import unittest
from unittest.mock import patch

from scripts import update_language_stats as stats


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "name": "sample-app",
            "full_name": "jorgeezequiel/sample-app",
            "owner": {"login": "jorgeezequiel"},
            "private": False,
            "archived": False,
            "fork": False,
            "topics": [],
            "description": "A small software project",
        }

    def test_accepts_owned_public_software_repository(self):
        self.assertTrue(stats.is_eligible(self.base))

    def test_rejects_private_repository(self):
        repo = {**self.base, "private": True}
        self.assertFalse(stats.is_eligible(repo))

    def test_rejects_archived_and_forked_repositories(self):
        self.assertFalse(stats.is_eligible({**self.base, "archived": True}))
        self.assertFalse(stats.is_eligible({**self.base, "fork": True}))

    def test_rejects_privacy_and_documentation_repositories(self):
        self.assertFalse(stats.is_eligible({**self.base, "name": "privacy-policy-site"}))
        self.assertFalse(stats.is_eligible({**self.base, "topics": ["documentation-only"]}))
        self.assertFalse(stats.is_eligible({**self.base, "description": "Privacy policy website"}))

    def test_rejects_other_owners(self):
        self.assertFalse(stats.is_eligible({**self.base, "owner": {"login": "someone-else"}}))


class ReadmeTests(unittest.TestCase):
    def test_stats_are_aggregated_and_image_is_switched_after_success(self):
        current = (
            "Intro\n![Language statistics preview](assets/language-stats.svg)\n"
            + stats.START + "\nplaceholder\n" + stats.END + "\n"
        )
        result = stats.updated_readme(current, {"Python": 75, "Dart": 25}, 2)
        self.assertIn("Eligible public software repositories:** 2", result)
        self.assertIn("| Python | 75.0% |", result)
        self.assertIn("| Dart | 25.0% |", result)
        self.assertIn("assets/language-stats.gif", result)
        self.assertNotIn("placeholder", result)

    def test_missing_markers_fail_closed(self):
        with self.assertRaises(RuntimeError):
            stats.updated_readme("No markers here", {"Python": 10}, 1)

    def test_empty_language_data_does_not_render(self):
        with patch.object(stats, "eligible_repositories", return_value=[{"full_name": "x"}]), \
             patch.object(stats, "language_totals", return_value={}):
            with patch.object(stats, "publish_outputs") as publish:
                with self.assertRaises(SystemExit) as result:
                    stats.main()
                self.assertEqual(result.exception.code, 1)
                publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
