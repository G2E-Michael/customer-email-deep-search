import struct
import unittest

from ceds.dnsx import _read_name, domain_health


class ReadNameTest(unittest.TestCase):
    def test_plain_name(self):
        data = b"\x04test\x03com\x00"
        name, off = _read_name(data, 0)
        self.assertEqual(name, "test.com")
        self.assertEqual(off, len(data))

    def test_pointer(self):
        # 0..12 是前缀垃圾，12 处放 "test.com"，0 处放指向 12 的指针
        tail = b"\x04test\x03com\x00"
        data = b"\xc0\x0c" + b"\x00" * 10 + tail
        name, off = _read_name(data, 0)
        self.assertEqual(name, "test.com")
        self.assertEqual(off, 2)


class HealthShapeTest(unittest.TestCase):
    def test_state_is_known_value(self):
        health = domain_health("example.com", timeout=2.0)
        if health["state"] == "dead" and health.get("error"):
            self.skipTest("DNS 不可达: %s" % health["error"])
        self.assertIn(health["state"], {"mx", "a_only", "null_mx", "dead"})
        self.assertIn("mx", health)


if __name__ == "__main__":
    unittest.main()
