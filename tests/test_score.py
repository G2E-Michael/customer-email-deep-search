import unittest

from ceds.score import classify, grade, score_address


class ClassifyTest(unittest.TestCase):
    def test_role(self):
        self.assertEqual(classify("info"), "role")
        self.assertEqual(classify("kontakt"), "role")
        self.assertEqual(classify("customerservice"), "role")

    def test_named(self):
        self.assertEqual(classify("michael.yang"), "named")
        self.assertEqual(classify("schauder"), "named")

    def test_numeric_suffix_of_role_is_role(self):
        self.assertEqual(classify("info2"), "role")


class GradeTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(grade(70), "A")
        self.assertEqual(grade(69), "B")
        self.assertEqual(grade(45), "B")
        self.assertEqual(grade(44), "C")


class ScoreTest(unittest.TestCase):
    def test_official_beats_third_party(self):
        official = score_address("info@firma.de", "official", ["https://firma.de/kontakt"], "mx")
        third = score_address("info@firma.de", "third_party", ["https://dir.example/x"], "mx")
        self.assertGreater(official, third)

    def test_more_sources_score_higher(self):
        one = score_address("info@firma.de", "official", ["a"], "mx")
        three = score_address("info@firma.de", "official", ["a", "b", "c"], "mx")
        self.assertGreater(three, one)

    def test_dead_domain_tanks(self):
        alive = score_address("info@firma.de", "official", ["a"], "mx")
        dead = score_address("info@firma.de", "official", ["a"], "dead")
        self.assertLess(dead, alive)

    def test_score_bounds(self):
        self.assertLessEqual(score_address("a.b@firma.de", "official", ["a"] * 9, "mx"), 100)
        self.assertGreaterEqual(score_address("a.b@firma.de", "inferred", [], "dead"), 0)


if __name__ == "__main__":
    unittest.main()
