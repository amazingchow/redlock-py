# -*- coding: utf-8 -*-
import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "redlock"))

import logging
import redis
import unittest

from redlock import Redlock, Lock


class RedlockTestCase(unittest.TestCase):
    logger = logging.getLogger(__name__)

    def setUp(self):
        self.redis_connection = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            password="sOmE_sEcUrE_pAsS",
            socket_timeout=0.5,
        )
        if self.redis_connection.ping():
            self.logger.info("Redis connection established.")
            self.redlock = Redlock(connections=[self.redis_connection], async_mode=False)
        else:
            self.logger.error("Redis connection failed.")
            self.redlock = None
    
    def test_lock_and_unlock(self):
        if self.redlock is None:
            self.skipTest("Redis connection failed.")
        resource = "test_resource"
        ttl = 2000
        success, lock = self.redlock.lock(resource, ttl)
        self.assertTrue(success)
        self.assertIsInstance(lock, Lock)
        self.assertTrue(lock.validity > 0)
        self.assertTrue(lock.resource == "test_resource")
        success = self.redlock.unlock(lock)
        self.assertTrue(success)

    def test_extend(self):
        if self.redlock is None:
            self.skipTest("Redis connection failed.")
        resource = "test_resource_2"
        ttl = 2000
        success, lock = self.redlock.lock(resource, ttl)
        self.assertTrue(success)
        self.assertIsInstance(lock, Lock)
        self.assertTrue(lock.validity > 0)
        self.assertTrue(lock.resource == "test_resource_2")
        ttl = 2000
        success = self.redlock.extend(lock, ttl)
        self.assertTrue(success)
        success = self.redlock.unlock(lock)
        self.assertTrue(success)

    def tearDown(self):
        if self.redlock is not None:
            self.redis_connection.close()


if __name__ == "__main__":
    unittest.main()
