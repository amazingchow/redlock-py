# -*- coding: utf-8 -*-
import sys
sys.path.append('.')

import unittest

from redlock import Redlock


class TestRedlock(unittest.TestCase):

    def setUp(self):
        self.redlock = Redlock([{"host": "localhost", "port": 6379, "password": "sOmE_sEcUrE_pAsS", "socket_timeout": 0.5}])

    def test_lock(self):
        lock = self.redlock.lock("pants", 100)
        self.assertEqual(lock.resource, "pants")
        self.redlock.unlock(lock)
        lock = self.redlock.lock("pants", 10)
        self.assertEqual(lock.resource, "pants")
        self.redlock.unlock(lock)

    def test_blocked(self):
        lock = self.redlock.lock("pants", 1000)
        self.assertEqual(lock.resource, "pants")
        bad = self.redlock.lock("pants", 10)
        self.assertFalse(bad)
        self.redlock.unlock(lock)


if __name__ == "__main__":
    unittest.main()
