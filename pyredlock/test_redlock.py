# -*- coding: utf-8 -*-
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import unittest

from pyredlock import RedisClient
from pyredlock import Redlock, Lock


class RedlockTestCase(unittest.TestCase):
    logger = logging.getLogger(__name__)

    def setUp(self):
        self.redis_client = RedisClient(client_conf={
            "endpoint": "localhost:6379",
            "password": "sOmE_sEcUrE_pAsS",
            "db": 0,
            "socket_timeout": 0.5,
            "socket_connect_timeout": 0.25
        })
        connected = self.redis_client.is_connected()
        if connected:
            self.logger.info("Redis connection established.")
            self.redlock = Redlock(connections=[self.redis_client.get_connection()], async_mode=False)
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
            self.redis_client.close()


if __name__ == "__main__":
    unittest.main()
