# -*- coding: utf-8 -*-
import asyncio
import random
import redis
import redis.asyncio as aio_redis
import redis.exceptions as redis_exceptions
import string
import time

from collections import namedtuple
from loguru import logger as loguru_logger
from typing import List, Optional, Tuple, Union

Lock = namedtuple("Lock", ("validity", "resource", "val"))


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
    """A distributed lock implementation using Redis."""

    def __init__(
            self,
            connections: List[Union[redis.Redis, aio_redis.Redis]],
            async_mode: bool = True,
            retry_count: float = None,
            retry_delay: float = None
        ):
        """
        Initialize the Redlock instance.

        Args:
            connections (List[Union[redis.Redis, aio_redis.Redis]]): List of Redis connections.
            async_mode (bool, optional): Whether to use asynchronous mode. Defaults to True.
            retry_count (float, optional): Number of retry attempts. Defaults to None.
            retry_delay (float, optional): Delay between retry attempts in seconds. Defaults to None.

        Attributes:
            _async_mode (bool): Whether asynchronous mode is enabled.
            _servers (List[Union[redis.Redis, aio_redis.Redis]]): List of Redis connections.
            _quorum (int): Quorum value for determining lock validity.
            retry_count (float): Number of retry attempts.
            retry_delay (float): Delay between retry attempts in seconds.
            _clock_drift_factor (float): Clock drift factor for calculating lock validity.
            _unlock_script (str): Lua script to unlock a resource.
            _extend_script (str): Lua script to extend the lock.

        Notes:
            N Redis servers are peers and do not differentiate between master and slave relationships.
            The quorum is calculated as follows:
                quorum = (len(connections) // 2) + 1
            This ensures that the majority of the Redis servers are online and reachable.
            For example, if there are 5 Redis servers, the quorum is 3.
            If 3 or more Redis servers are online and reachable, the lock is valid.
            If 2 or less Redis servers are online and reachable, the lock is invalid.
            The quorum value can be adjusted based on the number of Redis servers.
            For example, if there are 7 Redis servers, the quorum can be set to 4.
            If 4 or more Redis servers are online and reachable, the lock is valid.
            If 3 or less Redis servers are online and reachable, the lock is invalid.
            We recommend that the number of Redis servers be an odd number.

            We also recommend that the socket_timeout option be set the same for all Redis servers,
            and be much less than the lock validity time.
        """

        self._async_mode = async_mode
        self._servers = connections
        self._quorum = (len(connections) // 2) + 1

        default_retry_count = 3
        self.retry_count = retry_count or default_retry_count
        default_retry_delay = 0.2
        self.retry_delay = retry_delay or default_retry_delay
        self._clock_drift_factor = 0.01

        self._unlock_script = """if redis.call("GET",KEYS[1]) == ARGV[1] then
    return redis.call("DEL",KEYS[1])
else
    return 0
end"""
        self._extend_script = """if redis.call("GET",KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE",KEYS[1],ARGV[2])
else
    return 0
end"""

    async def _alock_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        try:
            assert isinstance(ttl, int), "ttl {} is not an integer".format(ttl)
        except AssertionError as e:
            raise ValueError(str(e))
        return await server.execute_command(f"SET {resource} {val} NX PX {ttl}") == b"OK"

    def _lock_instance(
            self,
            server: redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        try:
            assert isinstance(ttl, int), "ttl {} is not an integer".format(ttl)
        except AssertionError as e:
            raise ValueError(str(e))
        return server.execute_command(f"SET {resource} {val} NX PX {ttl}") == b"OK"

    async def _aunlock_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str
        ) -> bool:
        return await server.execute_command("EVAL", self._unlock_script, 1, resource, val) == 1

    def _unlock_instance(
            self,
            server: redis.Redis,
            resource: str,
            val: str
        ) -> bool:
        return server.execute_command("EVAL", self._unlock_script, 1, resource, val) == 1

    async def _aextend_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        return await server.execute_command("EVAL", self._extend_script, 1, resource, val, ttl) == 1

    def _extend_instance(
            self,
            server: aio_redis.Redis,
            resource: str,
            val: str,
            ttl: int
        ) -> bool:
        return server.execute_command("EVAL", self._extend_script, 1, resource, val, ttl) == 1

    def _get_unique_id(self) -> str:
        """
        Generate a unique identifier for the lock.

        Returns:
            str: Unique identifier.
        """
        CHARACTERS = string.ascii_letters + string.digits
        return "".join([random.choice(CHARACTERS) for _ in range(22)])

    async def alock(self, resource: str, ttl: int) -> Tuple[bool, Optional[Lock]]:
        """
        Acquire a lock on a resource asynchronously.

        Args:
            resource (str): Resource to lock.
            ttl (int): Time-to-live for the lock in milliseconds.

        Returns:
            Tuple[bool, Optional[Lock]]: A tuple containing a boolean indicating whether the lock is acquired successfully and an optional Lock object.

        Notes:
            "SET resource_name my_random_value NX PX 30000" is equivalent to "SETNX resource_name my_random_value; PEXPIRE resource_name 30000", but former one is atomic.

            Consider the following scenarios that can lead to deadlock:
                1. SETNX executed successfully, but the execution of EXPIRE failed due to a network issue.
                2. SETNX executed successfully, but Redis experienced an unexpected crash, and EXPIRE didn't have a chance to execute.
                3. SETNX executed successfully, but the client crashed unexpectedly, and EXPIRE didn't have a chance to execute either.
            In the above three scenarios, the lock will never expire, and the resource will be locked forever.
            
            Thanks to atomicity, we can avoid the problem of not setting the expiration time.

            We've solved the problem of setting the expiration time, but there's another problem.

            Consider the following scenario:
                1. Lock expired: Client 1 took too long to operate on the shared resource, resulting in the lock being automatically released and subsequently acquired by Client 2.
                2. Releasing someone else's lock: After Client 1 finished operating on the shared resource, it mistakenly released the lock held by Client 2.

            The first issue may be caused by inaccurate assessment of the time required for sharing operational resources.
            Solution for first issue:
                Extend the lock time before the lock expires. When locking for the first time, set a reasonable expiration time.
                At the same time, we need to start a watchdog thread responsible for periodically checking the expiration time of the lock.
                If the lock is about to expire and the current worker thread has not finished operating the shared resource,
                the watchdog thread will automatically renew the lock by resetting the expiration time.

            The second issue may be due to the worker thread not checking if it still owns the lock when releasing it.
            Solution for second issue:
                The client (the worker thread) sets a "unique identifier" that only it knows when locking.
                Afterwards, when releasing the lock, it is necessary to first determine whether the lock' value is the same as the "unique identifier" formerly set by the client.

            We can write this deletion logic as a Lua script to guarantee atomicity. Redis processes each request in a "single-threaded" manner,
            when executing a Lua script, other requests must wait until the Lua script is finished processing.
            The Lua script ensures that no other commands are inserted between GET and DEL.

            Why do we need to operate on all nodes when releasing a lock?
            Let's say a client successfully acquires a lock on a Redis instance, but due to a network issue, it fails to read the response.
            In this case, the lock has actually been successfully acquired on Redis.
            Therefore, when releasing the lock, it is necessary to release the lock on "all nodes" regardless of whether it was successfully acquired before,
            in order to ensure that any "residual" locks on the nodes are cleaned up.

            ----------------------------
            How to correctly use distributed locks?

                1. By using distributed locks, the "mutual exclusion" objective is achieved at the higher level.
                   Although there can be extreme cases where the lock fails, it effectively blocks concurrent requests at the topmost level,
                   reducing the pressure on the operational resource layer to the maximum extent possible.
                2. However, for business scenarios that require absolute data correctness,
                   it is essential to have a solid "fallback" strategy at the resource layer.
                   The design approach can take inspiration from the concept of "fencing tokens" menthioned by Martin Kleppmann,
                   where data is updated at the database layer using versioning to avoid concurrent conflicts.
            """
        retry = 0
        val = self._get_unique_id()

        # Add 2 milliseconds to the drift to account for Redis expires
        # precision, which is 1 millisecond, plus 1 millisecond min
        # drift for small TTLs.
        clock_drift = int(ttl * self._clock_drift_factor) + 2

        redis_errors = []
        restart_attempt = True
        while restart_attempt:
            n = 0
            del redis_errors[:]

            t1 = int(time.time() * 1000)
            for server in self._servers:
                try:
                    ok = await self._alock_instance(server, resource, val, ttl)
                    if ok:
                        n += 1
                except redis_exceptions.RedisError as e:
                    redis_errors.append(e)
            t2 = int(time.time() * 1000)
            
            validity = int(ttl - (t2 - t1) - clock_drift)
            if n >= self._quorum and validity > 0:
                if len(redis_errors) > 0:
                    loguru_logger.error(f"Redlock Lock Error:{MultipleRedlockException(redis_errors)}")
                return (True, Lock(validity, resource, val))
            else:
                for server in self._servers:
                    try:
                        await self._aunlock_instance(server, resource, val)
                    except Exception:
                        pass
                retry += 1
                restart_attempt = retry < self.retry_count
                if restart_attempt:
                    await asyncio.sleep(self.retry_delay)
        return (False, None)

    def lock(self, resource: str, ttl: int) -> Tuple[bool, Optional[Lock]]:
        """
        Acquire a lock on a resource.

        Args:
            resource (str): Resource to lock.
            ttl (int): Time-to-live for the lock in milliseconds.

        Returns:
            Tuple[bool, Optional[Lock]]: A tuple containing a boolean indicating whether the lock is acquired successfully and an optional Lock object.
        """
        retry = 0
        val = self._get_unique_id()

        # Add 2 milliseconds to the drift to account for Redis expires
        # precision, which is 1 millisecond, plus 1 millisecond min
        # drift for small TTLs.
        clock_drift = int(ttl * self._clock_drift_factor) + 2

        redis_errors = []
        restart_attempt = True
        while restart_attempt:
            n = 0
            del redis_errors[:]

            t1 = int(time.time() * 1000)
            for server in self._servers:
                try:
                    ok = self._lock_instance(server, resource, val, ttl)
                    if ok:
                        n += 1
                except redis_exceptions.RedisError as e:
                    redis_errors.append(e)
            t2 = int(time.time() * 1000)
            
            validity = int(ttl - (t2 - t1) - clock_drift)
            if n >= self._quorum and validity > 0:
                if len(redis_errors) > 0:
                    loguru_logger.error(f"Redlock Lock Error:{MultipleRedlockException(redis_errors)}")
                return (True, Lock(validity, resource, val))
            else:
                for server in self._servers:
                    try:
                        self._unlock_instance(server, resource, val)
                    except Exception:
                        pass
                retry += 1
                restart_attempt = retry < self.retry_count
                if restart_attempt:
                    time.sleep(self.retry_delay)
        return (False, None)

    async def aunlock(self, lock: Lock) -> bool:
        """
        Release a lock on a resource asynchronously.

        Args:
            lock (Lock): Lock object to release.

        Returns:
            bool: True if the lock is released successfully, False otherwise.
        """
        redis_errors = []
        for server in self._servers:
            try:
                await self._aunlock_instance(server, lock.resource, lock.val)
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Unlock Error:{MultipleRedlockException(redis_errors)}")
            return False
        return True

    def unlock(self, lock: Lock) -> bool:
        """
        Release a lock on a resource.

        Args:
            lock (Lock): Lock object to release.

        Returns:
            bool: True if the lock is released successfully, False otherwise.
        """
        redis_errors = []
        for server in self._servers:
            try:
                self._unlock_instance(server, lock.resource, lock.val)
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Unlock Error:{MultipleRedlockException(redis_errors)}")
            return False
        return True

    async def aextend(self, lock: Lock, ttl: int) -> bool:
        """
        Extend the validity of a lock on a resource asynchronously.

        Args:
            lock (Lock): Lock object to extend.
            ttl (int): New time-to-live for the lock in milliseconds.

        Returns:
            bool: True if the lock is extended successfully, False otherwise.
        """
        redis_errors = []
        n = 0
        for server in self._servers:
            try:
                ok = await self._aextend_instance(server, lock.resource, lock.val, ttl)
                if ok:
                    n += 1
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Extend Error:{MultipleRedlockException(redis_errors)}")
        return n >= self._quorum

    def extend(self, lock: Lock, ttl: int) -> bool:
        """
        Extend the validity of a lock on a resource.

        Args:
            lock (Lock): Lock object to extend.
            ttl (int): New time-to-live for the lock in milliseconds.

        Returns:
            bool: True if the lock is extended successfully, False otherwise.
        """
        redis_errors = []
        n = 0
        for server in self._servers:
            try:
                ok = self._extend_instance(server, lock.resource, lock.val, ttl)
                if ok:
                    n += 1
            except redis_exceptions.RedisError as e:
                redis_errors.append(e)
        if len(redis_errors) > 0:
            loguru_logger.error(f"Redlock Extend Error:{MultipleRedlockException(redis_errors)}")
        return n >= self._quorum
