# -*- coding: utf-8 -*-
import logging
import random
import redis
import string
import sys
import time

from collections import namedtuple
from redis.exceptions import RedisError

_g_logger = logging.getLogger("redlock")
_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.INFO)
_formatter = logging.Formatter(
    fmt="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_handler.setFormatter(_formatter)
_g_logger.addHandler(_handler)
_g_logger.setLevel(logging.INFO)
_g_logger.propagate = False

Lock = namedtuple("Lock", ("validity", "resource", "key"))


class CannotObtainLock(Exception):
    pass


class MultipleRedlockException(Exception):
    def __init__(self, errors, *args, **kwargs):
        super(MultipleRedlockException, self).__init__(*args, **kwargs)
        self.errors = errors

    def __str__(self):
        return " :: ".join([str(e) for e in self.errors])

    def __repr__(self):
        return self.__str__()


class Redlock(object):

    def __init__(self, connection_list: list, retry_count=None, retry_delay=None):
        self._servers = []
        for connection_info in connection_list:
            try:
                if isinstance(connection_info, str):
                    server = redis.StrictRedis.from_url(connection_info)
                elif type(connection_info) == dict:
                    server = redis.StrictRedis(**connection_info)
                else:
                    server = connection_info
                self._servers.append(server)
            except Exception as e:
                raise Warning(str(e))
        self._quorum = (len(connection_list) // 2) + 1
        if len(self._servers) < self._quorum:
            raise CannotObtainLock("Failed to connect to the majority of redis servers")
        _g_logger.info("Server Quorum:{}".format(len(self._servers)))

        default_retry_count = 3
        self.retry_count = retry_count or default_retry_count
        default_retry_delay = 0.2
        self.retry_delay = retry_delay or default_retry_delay
        self._clock_drift_factor = 0.01
        self._unlock_script = """if redis.call("get",KEYS[1]) == ARGV[1] then
    return redis.call("del",KEYS[1])
else
    return 0
end"""
        
        self._extend_script = """if redis.call("get",KEYS[1]) == ARGV[1] then
    return redis.call("pexpire",KEYS[1],ARGV[2])
else
    return 0
end"""

    def _lock_instance(self, server, resource, val, ttl):
        try:
            assert isinstance(ttl, int), "ttl {} is not an integer".format(ttl)
        except AssertionError as e:
            raise ValueError(str(e))
        return server.set(resource, val, nx=True, px=ttl)

    def _unlock_instance(self, server, resource, val):
        try:
            server.eval(self._unlock_script, 1, resource, val)
        except Exception:
            _g_logger.exception("Error unlocking resource %s in server %s", resource, str(server))

    def _extend_instance(self, server, resource, val, ttl):
        try:
            return server.eval(self._extend_script, 1, resource, val, ttl) == 1
        except Exception:
            logging.exception("Error extending lock on resource %s in server %s", resource, str(server))
            return False

    def _test_instance(self, server, resource):
        try:
            return server.get(resource) is not None
        except:
            logging.exception("Error reading lock on resource %s in server %s", resource, str(server))

    def _get_unique_id(self):
        CHARACTERS = string.ascii_letters + string.digits
        return "".join(random.choice(CHARACTERS) for _ in range(22)).encode()

    def lock(self, resource, ttl):
        retry = 0
        val = self._get_unique_id()

        # Add 2 milliseconds to the drift to account for Redis expires
        # precision, which is 1 millisecond, plus 1 millisecond min
        # drift for small TTLs.
        drift = int(ttl * self._clock_drift_factor) + 2

        redis_errors = []
        restart_attempt = True
        while restart_attempt:
            n = 0
            start_time = int(time.time() * 1000)
            del redis_errors[:]
            for server in self._servers:
                try:
                    if self._lock_instance(server, resource, val, ttl):
                        n += 1
                except RedisError as e:
                    redis_errors.append(e)
            elapsed_time = int(time.time() * 1000) - start_time
            validity = int(ttl - elapsed_time - drift)
            if validity > 0 and n >= self._quorum:
                if len(redis_errors) > 0:
                    raise MultipleRedlockException(redis_errors)
                return Lock(validity, resource, val)
            else:
                for server in self._servers:
                    try:
                        self._unlock_instance(server, resource, val)
                    except:
                        pass
                retry += 1
                restart_attempt = retry < self.retry_count
                if restart_attempt:
                    time.sleep(self.retry_delay)
        return False

    def unlock(self, lock):
        redis_errors = []
        for server in self._servers:
            try:
                self._unlock_instance(server, lock.resource, lock.key)
            except RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            raise MultipleRedlockException(redis_errors)

    def extend(self, lock, ttl):
        redis_errors = []
        n = 0
        for server in self._servers:
            try:
                if self._extend_instance(server, lock.resource, lock.key, ttl):
                    n += 1
            except RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            raise MultipleRedlockException(redis_errors)
        return n >= self._quorum

    def test(self, resource):
        redis_errors = []
        lock = Lock(0, resource, None)
        n = 0
        for server in self._servers:
            try:
                if self._test_instance(server, lock.resource):
                    n += 1
            except RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            raise MultipleRedlockException(redis_errors)
        return n >= self._quorum
