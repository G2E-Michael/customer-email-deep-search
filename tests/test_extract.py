import unittest

from ceds.extract import extract, is_plausible, normalize


class NormalizeTest(unittest.TestCase):
    def test_bracket_at_and_dot(self):
        text = "Vertrieb: max [at] firma [dot] de"
        self.assertIn("@firma", normalize(text))

    def test_html_entity(self):
        self.assertIn("info@firma.de", normalize("info&#64;firma.de"))

    def test_percent40(self):
        self.assertIn("info@firma.de", normalize("info%40firma.de"))


class ExtractTest(unittest.TestCase):
    def test_only_own_domain(self):
        text = "info@firma.de, partner@other.de, sales@sub.firma.de"
        self.assertEqual(extract(text, "firma.de"),
                         ["info@firma.de", "sales@sub.firma.de"])

    def test_no_substring_domain_match(self):
        # notfirma.de 不能被当成 firma.de
        self.assertEqual(extract("x@notfirma.de", "firma.de"), [])

    def test_trailing_punctuation(self):
        self.assertEqual(extract("Schreiben Sie an info@firma.de.", "firma.de"),
                         ["info@firma.de"])

    def test_placeholder_rejected(self):
        self.assertEqual(extract("john.doe@firma.de", "firma.de"), [])
        self.assertEqual(extract("max.mustermann@firma.de", "firma.de"), [])

    def test_image_filename_still_yields_address(self):
        # 图片文件名里嵌地址时，扩展名不会被当成域名的一部分
        self.assertEqual(extract("logo@firma.de.png", "firma.de"), ["logo@firma.de"])

    def test_dedupe_keeps_order(self):
        text = "bb@firma.de aa@firma.de bb@firma.de"
        self.assertEqual(extract(text, "firma.de"), ["bb@firma.de", "aa@firma.de"])


class PlausibleTest(unittest.TestCase):
    def test_rejects_abuse(self):
        self.assertFalse(is_plausible("abuse@firma.de"))

    def test_rejects_short_local(self):
        self.assertFalse(is_plausible("a@firma.de"))

    def test_accepts_normal(self):
        self.assertTrue(is_plausible("kontakt@firma.de"))


if __name__ == "__main__":
    unittest.main()
