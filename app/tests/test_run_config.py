import os
import tempfile
import unittest

from app.run import load_dotenv


class LoadDotenvTest(unittest.TestCase):
    def tearDown(self):
        for key in ("PG_TEST_A", "PG_TEST_B", "PG_TEST_EXISTING"):
            os.environ.pop(key, None)

    def test_parses_values_comments_and_export(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as source:
            source.write("# comment\nPG_TEST_A=hello\n")
            source.write("export PG_TEST_B='quoted value'\n")
            path = source.name
        try:
            loaded = load_dotenv(path)
        finally:
            os.unlink(path)
        self.assertEqual(loaded["PG_TEST_A"], "hello")
        self.assertEqual(loaded["PG_TEST_B"], "quoted value")
        self.assertEqual(os.environ["PG_TEST_A"], "hello")

    def test_does_not_override_existing_environment(self):
        os.environ["PG_TEST_EXISTING"] = "real"
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as source:
            source.write("PG_TEST_EXISTING=from-file\n")
            path = source.name
        try:
            loaded = load_dotenv(path)
        finally:
            os.unlink(path)
        self.assertEqual(os.environ["PG_TEST_EXISTING"], "real")
        self.assertNotIn("PG_TEST_EXISTING", loaded)

    def test_missing_file_is_ignored(self):
        self.assertEqual(load_dotenv("/tmp/definitely-missing-power-guardian.env"), {})


if __name__ == "__main__":
    unittest.main()
