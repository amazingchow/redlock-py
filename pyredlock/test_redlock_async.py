# -*- coding: utf-8 -*-
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import unittest

from pyredlock import AioRedisClient
from pyredlock import Redlock, Lock


class RedlockTestCase(unittest.IsolatedAsyncioTestCase):
    logger = logging.getLogger(__name__)

    async def asyncSetUp(self):
        self.redis_client = AioRedisClient(client_conf={
            "endpoint": "localhost:6379",
            "password": "sOmE_sEcUrE_pAsS",
            "db": 0,
            "socket_timeout": 0.5,
            "socket_connect_timeout": 0.25
        })
        connected = await self.redis_client.is_connected()
        if connected:
            self.logger.info("Redis connection established.")
            self.redlock = Redlock(connections=[self.redis_client.get_connection()], async_mode=True)
        else:
            self.logger.error("Redis connection failed.")
            self.redlock = None
    
    async def test_lock_and_unlock(self):
        if self.redlock is None:
            self.skipTest("Redis connection failed.")
        resource = "test_resource"
        ttl = 2000
        success, lock = await self.redlock.alock(resource, ttl)
        self.assertTrue(success)
        self.assertIsInstance(lock, Lock)
        self.assertTrue(lock.validity > 0)
        self.assertTrue(lock.resource == "test_resource")
        success = await self.redlock.aunlock(lock)
        self.assertTrue(success)

    async def test_extend(self):
        if self.redlock is None:
            self.skipTest("Redis connection failed.")
        resource = "test_resource_2"
        ttl = 2000
        success, lock = await self.redlock.alock(resource, ttl)
        self.assertTrue(success)
        self.assertIsInstance(lock, Lock)
        self.assertTrue(lock.validity > 0)
        self.assertTrue(lock.resource == "test_resource_2")
        ttl = 2000
        success = await self.redlock.aextend(lock, ttl)
        self.assertTrue(success)
        success = await self.redlock.aunlock(lock)
        self.assertTrue(success)

    async def asyncTearDown(self):
        if self.redlock is not None:
            await self.redis_client.close()


if __name__ == "__main__":
    unittest.main()
