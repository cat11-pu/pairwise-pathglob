"""Acceptance tests for the pathglob matching kernel.

Run them from the project root with:

    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathglob import (
    PatternSyntaxError,
    compile_pattern,
    filter_paths,
    match_any,
    matches,
    normalize,
)


class LiteralTest(unittest.TestCase):
    def test_literal_components_match_a_whole_path(self):
        self.assertTrue(matches("readme.md", "readme.md"))
        self.assertFalse(matches("readme.md", "README.MD"))
        self.assertFalse(matches("readme.md", "readme.md.bak"))
        self.assertFalse(matches("readme.md", "readme"))
        self.assertTrue(matches("src/kernel/core.py", "src/kernel/core.py"))
        self.assertFalse(matches("src/kernel/core.py", "src/kernel/core.python"))
        self.assertFalse(matches("src/kernel/core.py", "other/kernel/core.py"))
        self.assertTrue(matches("a/b/c", "a/b/c"))
        self.assertFalse(matches("a/b/c", "a/b"))
        self.assertFalse(matches("a/b", "a/b/c"))
        self.assertFalse(matches("a/b", "ab"))
        self.assertFalse(matches("ab", "a/b"))
        self.assertFalse(matches("a b", "a/b"))


class WildcardTest(unittest.TestCase):
    def test_a_star_and_a_question_mark_stay_inside_one_component(self):
        self.assertTrue(matches("src/*.py", "src/main.py"))
        self.assertFalse(matches("src/*.py", "src/nested/main.py"))
        self.assertFalse(matches("src/*.py", "src/a/b.py"))
        self.assertFalse(matches("*.txt", "a/b.txt"))
        self.assertTrue(matches("src/*/*.py", "src/pkg/mod.py"))
        self.assertFalse(matches("src/*/*.py", "src/pkg/sub/mod.py"))
        self.assertFalse(matches("src/*/*.py", "src/mod.py"))
        self.assertTrue(matches("a*c", "ac"))
        self.assertTrue(matches("a*c", "abbbc"))
        self.assertFalse(matches("a*c", "ab/c"))
        self.assertFalse(matches("a*c", "c"))
        self.assertTrue(matches("?.txt", "a.txt"))
        self.assertTrue(matches("?.txt", "z.txt"))
        self.assertFalse(matches("?.txt", ".txt"))
        self.assertFalse(matches("?.txt", "ab.txt"))
        self.assertTrue(matches("a/?.txt", "a/b.txt"))
        self.assertFalse(matches("a/?.txt", "a/.txt"))
        self.assertFalse(matches("a?b", "a/b"))
        self.assertFalse(matches("a?", "a"))


class GlobstarTest(unittest.TestCase):
    def test_a_globstar_crosses_directories(self):
        self.assertTrue(matches("**/*.py", "a/b/main.py"))
        self.assertTrue(matches("**/*.py", "main.py"))
        self.assertFalse(matches("**/*.py", "a/b/main.pyc"))
        self.assertTrue(matches("a/**/z.txt", "a/z.txt"))
        self.assertTrue(matches("a/**/z.txt", "a/b/z.txt"))
        self.assertTrue(matches("a/**/z.txt", "a/b/c/z.txt"))
        self.assertFalse(matches("a/**/z.txt", "b/a/z.txt"))
        self.assertTrue(matches("a/**", "a/b"))
        self.assertTrue(matches("a/**", "a/b/c/d"))
        self.assertTrue(matches("a/**/*.py", "a/x/y/z.py"))
        self.assertTrue(matches("**", "whatever/deep/path.txt"))
        self.assertTrue(matches("**/core/*.py", "src/ab/core/main.py"))


class ClassTest(unittest.TestCase):
    def test_character_classes_select_inside_one_component(self):
        self.assertTrue(matches("file[0-9].txt", "file7.txt"))
        self.assertFalse(matches("file[0-9].txt", "filex.txt"))
        self.assertTrue(matches("file[a-c].txt", "filea.txt"))
        self.assertTrue(matches("file[a-c].txt", "filec.txt"))
        self.assertFalse(matches("file[a-c].txt", "filed.txt"))
        self.assertTrue(matches("file[!a-c].txt", "filed.txt"))
        self.assertFalse(matches("file[!a-c].txt", "fileb.txt"))
        self.assertTrue(matches("file[^0-9].txt", "filex.txt"))
        self.assertFalse(matches("file[^0-9].txt", "file3.txt"))
        self.assertTrue(matches("v[-ab]x", "v-x"))
        self.assertTrue(matches("v[ab-]x", "v-x"))
        self.assertTrue(matches(r"[a-c\-]x", "-x"))
        self.assertFalse(matches("file[0-9].txt", "file/.txt"))
        self.assertFalse(matches("file[!0-9].txt", "file/.txt"))
        self.assertFalse(matches("file[0-9].txt", "file77.txt"))


class EscapeTest(unittest.TestCase):
    def test_escapes_remove_the_wildcard_meaning(self):
        self.assertTrue(matches(r"a\?b", "a?b"))
        self.assertFalse(matches(r"a\?b", "axb"))
        self.assertFalse(matches(r"a\?b", "a?xb"))
        self.assertTrue(matches(r"a\*b", "a*b"))
        self.assertFalse(matches(r"a\*b", "a*xyb"))
        self.assertFalse(matches(r"a\*b", "ab"))
        self.assertTrue(matches(r"a\[b", "a[b"))
        self.assertFalse(matches(r"a\[b", "axb"))
        self.assertTrue(matches(r"a\ b", "a b"))
        self.assertFalse(matches(r"a\ b", "a  b"))
        self.assertTrue(matches("back\\\\slash", "back\\slash"))
        self.assertFalse(matches("back\\\\slash", "backslash"))
        self.assertFalse(matches(r"stars\*", "stars"))


class CaseStrategyTest(unittest.TestCase):
    def test_case_sensitivity_can_be_turned_off(self):
        self.assertFalse(matches("readme.md", "README.MD"))
        self.assertTrue(matches("readme.md", "README.MD", case_sensitive=False))
        self.assertFalse(matches("SRC/*.PY", "src/Main.py"))
        self.assertTrue(matches("SRC/*.PY", "src/Main.py", case_sensitive=False))
        self.assertTrue(matches("data/*.csv", "DATA/Sales.CSV", case_sensitive=False))
        self.assertFalse(matches("data/*.csv", "DATA/Sales.JSON", case_sensitive=False))
        compiled = compile_pattern("Notes/*.TXT", case_sensitive=False)
        self.assertTrue(compiled.matches("notes/todo.txt"))
        self.assertFalse(compiled.matches("other/todo.txt"))


class NormalizeTest(unittest.TestCase):
    def test_repeated_separators_and_dot_components_collapse(self):
        self.assertEqual(normalize("a//b///c"), "a/b/c")
        self.assertEqual(normalize("a/b/"), "a/b")
        self.assertEqual(normalize("./src/./main.py"), "src/main.py")
        self.assertEqual(normalize("/tmp//x/"), "tmp/x")
        self.assertTrue(matches("src//*.py", "src/main.py"))
        self.assertTrue(matches("src/*.py", "src//main.py"))
        self.assertTrue(matches("./src/*.py", "src/main.py"))
        self.assertTrue(matches("/etc/hosts", "etc/hosts"))
        self.assertTrue(matches("etc/hosts", "./etc///hosts"))
        self.assertFalse(matches("src/*.py", "src//main.py.bak"))


class PatternSetTest(unittest.TestCase):
    def test_several_patterns_and_repeated_paths(self):
        paths = ["main.py", "data.json", "README.md", "main.py", "notes.txt"]
        self.assertEqual(filter_paths(["*.md", "*.py"], paths), ["main.py", "README.md"])
        self.assertEqual(filter_paths([], paths), [])
        self.assertEqual(filter_paths(["*.json"], paths), ["data.json"])
        self.assertEqual(compile_pattern("*.py").filter(paths), ["main.py"])
        self.assertTrue(match_any(["*.md", "*.py"], "README.md"))
        self.assertTrue(match_any(["*.md", "*.py"], "main.py"))
        self.assertFalse(match_any(["*.md", "*.py"], "notes.txt"))
        self.assertFalse(match_any([], "notes.txt"))


class FilterTest(unittest.TestCase):
    def test_filtered_paths_follow_the_same_component_rules(self):
        paths = ["src/a.py", "src/pkg/b.py", "src/pkg/deep/c.py", "src/d.py", "src/a.py", "other/e.py"]
        self.assertEqual(filter_paths(["src/*.py"], paths), ["src/a.py", "src/d.py"])
        self.assertEqual(filter_paths(["src/**"], paths),
                         ["src/a.py", "src/pkg/b.py", "src/pkg/deep/c.py", "src/d.py"])
        self.assertEqual(filter_paths(["*.py"], paths), [])
        self.assertEqual(filter_paths(["**/b.py"], paths), ["src/pkg/b.py"])


class ErrorTest(unittest.TestCase):
    def test_malformed_patterns_are_rejected(self):
        bad_patterns = [
            "",
            "./",
            "[",
            "[abc",
            "[]",
            "[!]",
            "[z-a]",
            "[a/b]",
            r"[\]",
            "a\\",
            "src/a\\",
        ]
        for pattern in bad_patterns:
            with self.assertRaises(PatternSyntaxError):
                compile_pattern(pattern)
        with self.assertRaises(TypeError):
            compile_pattern(None)
        with self.assertRaises(TypeError):
            compile_pattern(42)
        with self.assertRaises(TypeError):
            matches("a", None)


if __name__ == "__main__":
    unittest.main()
