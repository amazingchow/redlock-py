# -*- coding: utf-8 -*-
import sys
sys.path.append('..')

import redis
import unittest

from redlock import Redlock


class TestRedlock(unittest.TestCase):

    def setUp(self):
        self.conn = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            password="sOmE_sEcUrE_pAsS",
            socket_timeout=0.5,
        )
        self.redlock = Redlock(connections=[self.conn], async_mode=False)

    def test_lock(self):
        ok, lock = self.redlock.lock("test_redlock_key", 60000)
        self.assertTrue(ok)
        self.assertEqual(lock.resource, "test_redlock_key")
        self.assertTrue(self.redlock.unlock(lock))
        ok, lock = self.redlock.lock("test_redlock_key", 60000)
        self.assertTrue(ok)
        self.assertEqual(lock.resource, "test_redlock_key")
        self.assertTrue(self.redlock.unlock(lock))

    def test_blocked(self):
        ok, lock = self.redlock.lock("test_redlock_key", 1000)
        self.assertTrue(ok)
        self.assertEqual(lock.resource, "test_redlock_key")
        ok, bad_lock = self.redlock.lock("test_redlock_key", 1000)
        self.assertFalse(ok)
        self.assertTrue(self.redlock.unlock(lock))

    def tearDown(self):
        self.conn.close()

if __name__ == "__main__":
    unittest.main()
