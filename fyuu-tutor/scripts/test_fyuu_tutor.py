#!/usr/bin/env python3
"""Small regression checks for Fyuu Tutor's shared guards and identity."""

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from build_index import recommended_entry
from project_config import PIPELINES, resolve_child, validate_config


ROOT = Path(__file__).resolve().parent.parent


class FyuuTutorChecks(unittest.TestCase):
    def test_child_path_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                resolve_child(temp, "../outside.md")

    def test_ambiguous_next_step_has_no_recommendation(self):
        entries = [Path("0004-a.html"), Path("0005-b.html")]
        self.assertIsNone(recommended_entry("先确认 0004–0005", entries))

    def test_skill_identity_and_direct_references(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: fyuu-tutor", skill)
        self.assertLess(len(skill.splitlines()), 500)
        for relative in (
            "references/core.md",
            "references/project-schema.md",
            "references/material-pipeline.md",
            "references/teaching-loop.md",
            "references/pipelines/capability.md",
            "references/pipelines/certification.md",
            "references/pipelines/language.md",
        ):
            self.assertIn(relative, skill)
            self.assertTrue((ROOT / relative).is_file())

    def test_schema_v2_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {
                "schema_version": 2,
                "project_id": "old",
                "display_name": "Old",
                "pipeline": "capability",
                "content_language": "en",
                "paths": {},
            }
            errors = validate_config(root, config, {"schema_version": 2, "capability": {}})
            self.assertIn("schema_version must be 3", errors)
            self.assertIn("pipeline.toml schema_version must be 3", errors)

    def test_pipeline_ids_share_one_dimension(self):
        self.assertEqual(PIPELINES, {"capability", "certification", "language"})

    def test_ui_kit_is_complete(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_lesson_ui.py"), "--kit"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_link_check_ignores_archived_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archived = root / "history" / "old.html"
            archived.parent.mkdir()
            archived.write_text('<link rel="stylesheet" href="missing.css">', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_links.py"), "--root", str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_create_validate_localize_and_claim_all_pipelines(self):
        scripts = ROOT / "scripts"
        kit_root = ROOT / "assets" / "ui-kit"
        source_snapshot = {path: path.read_bytes() for path in kit_root.rglob("*") if path.is_file()}
        themes = ("overview", "people", "process", "business", "review")
        smoke_index = 0
        with tempfile.TemporaryDirectory() as temp:
            projects = Path(temp) / "workspace" / "projects"
            for pipeline in sorted(PIPELINES):
                project = projects / f"{pipeline}-smoke"
                command = [
                    sys.executable, str(scripts / "create_project.py"),
                    "--root", str(projects), "--project-id", project.name,
                    "--display-name", pipeline.title(), "--pipeline", pipeline,
                ]
                if pipeline == "language":
                    command += ["--content-language", "zh-CN"]
                subprocess.run(command, check=True, capture_output=True, text=True)
                if pipeline == "certification":
                    (project / "sources" / "authority.md").write_text("# Test authority\n", encoding="utf-8")
                    (project / "pipeline.toml").write_text('''schema_version = 3

[certification]
exam_date = "2099-12-31"
target_score = 70
study_tracks = ["foundation"]
practice_start = "2099-01-01"
question_answer_status = "verified"
authority_version = "test"
authority_checked_on = "2099-01-01"
authority_review_due = "2099-12-01"
authority_url = "https://example.invalid/authority"
authority_source = "authority.md"
total_questions = 1
exam_minutes = 1
pretest_questions = 0
''', encoding="utf-8")
                subprocess.run(
                    [sys.executable, str(scripts / "validate_project.py"), "--project", str(project)],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    [sys.executable, str(scripts / "sync_ui_kit.py"), "--project", str(project), "--check"],
                    check=True, capture_output=True, text=True,
                )
                for page_format in ("lesson", "practice", "reference"):
                    template = (project / "outputs" / "templates" / f"{page_format}.html").read_text(encoding="utf-8")
                    html = re.sub(r"__[A-Z][A-Z0-9_]+__", "Test", template)
                    html = re.sub(r"\[[A-Za-z][^\]\n]* [^\]\n]*\]", "Test", html)
                    html = re.sub(r'data-pipeline="[^"]+"', f'data-pipeline="{pipeline}"', html, count=1)
                    html = re.sub(r'data-theme="[^"]+"', f'data-theme="{themes[smoke_index % len(themes)]}"', html, count=1)
                    folder = "reference" if page_format == "reference" else "lessons"
                    (project / "outputs" / folder / f"smoke-{page_format}.html").write_text(html, encoding="utf-8")
                    smoke_index += 1
                subprocess.run(
                    [sys.executable, str(scripts / "validate_lesson_ui.py"), "--project", str(project)],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    [sys.executable, str(scripts / "sync_ui_kit.py"), "--project", str(project), "--upgrade"],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    [sys.executable, str(scripts / "build_index.py"), "--project", str(project)],
                    check=True, capture_output=True, text=True,
                )
                html = (project / "outputs" / "index.html").read_text(encoding="utf-8")
                expected = "内容生产进度" if pipeline == "language" else "Production progress"
                self.assertIn(expected, html)

            project = projects / "capability-smoke"
            css_path = project / "outputs" / "assets" / "lesson.css"
            css = css_path.read_bytes()
            css_path.write_bytes(css + b"\n/* tampered */\n")
            result = subprocess.run(
                [sys.executable, str(scripts / "sync_ui_kit.py"), "--project", str(project), "--check"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            css_path.write_bytes(css)
            css_path.unlink()
            result = subprocess.run(
                [sys.executable, str(scripts / "sync_ui_kit.py"), "--project", str(project), "--check"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            css_path.write_bytes(css)
            subprocess.run(
                [sys.executable, str(scripts / "update_status.py"), "--project", str(project),
                 "--action", "claim", "--owner", "test", "--task", "smoke"],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                [sys.executable, str(scripts / "update_status.py"), "--project", str(project),
                 "--action", "release", "--owner", "test", "--next-step", "done"],
                check=True, capture_output=True, text=True,
            )
            status = (project / "STATUS.md").read_text(encoding="utf-8")
            self.assertEqual("idle", __import__("validate_project").status_value(status, "State"))
            self.assertEqual(source_snapshot, {path: path.read_bytes() for path in kit_root.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
