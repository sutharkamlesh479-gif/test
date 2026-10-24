import tempfile
import unittest
from pathlib import Path

from aurix_agent.tools import WorkspaceTools, ToolError


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "tests").mkdir()
        (self.root / "hello.py").write_text("print('hello')\n", encoding="utf-8")
        (self.root / "notes.txt").write_text("AURIX agent\nSafe testing\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_list_files(self):
        result = WorkspaceTools(self.root).list_files()
        self.assertIn("hello.py", result["files"])
        self.assertIn("notes.txt", result["files"])

    def test_read_file(self):
        result = WorkspaceTools(self.root).read_file("notes.txt")
        self.assertIn("AURIX agent", result["content"])

    def test_path_traversal_is_blocked(self):
        with self.assertRaises(ToolError):
            WorkspaceTools(self.root).read_file("../outside.txt")

    def test_sensitive_files_are_blocked(self):
        (self.root / ".env").write_text("API_KEY=private", encoding="utf-8")
        with self.assertRaises(ToolError):
            WorkspaceTools(self.root).read_file(".env")
        with self.assertRaises(ToolError):
            WorkspaceTools(self.root, allow_writes=True).write_file(".env", "API_KEY=overwrite")

    def test_write_needs_opt_in(self):
        with self.assertRaises(ToolError):
            WorkspaceTools(self.root).write_file("new.txt", "hello")

    def test_write_inside_workspace_when_enabled(self):
        result = WorkspaceTools(self.root, allow_writes=True).write_file("nested/new.txt", "hello")
        self.assertTrue(result["success"])
        self.assertEqual((self.root / "nested" / "new.txt").read_text(encoding="utf-8"), "hello")

    def test_python_syntax_check(self):
        result = WorkspaceTools(self.root).check_python("hello.py")
        self.assertTrue(result["success"])
        (self.root / "bad.py").write_text("def no(:\n", encoding="utf-8")
        self.assertFalse(WorkspaceTools(self.root).check_python("bad.py")["success"])

    def test_search_files(self):
        result = WorkspaceTools(self.root).search_files("safe")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["path"], "notes.txt")

    def test_test_execution_needs_opt_in(self):
        with self.assertRaises(ToolError):
            WorkspaceTools(self.root).run_tests()


if __name__ == "__main__":
    unittest.main()
