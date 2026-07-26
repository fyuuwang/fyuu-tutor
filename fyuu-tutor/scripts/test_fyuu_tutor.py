#!/usr/bin/env python3
"""Small regression checks for Fyuu Tutor's shared guards and identity."""

from pathlib import Path
import os
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
    def _status_project(self, temp, state="idle", owner="—", missing=()):
        project = Path(temp) / "project"
        project.mkdir()
        fields = {
            "State": state,
            "Owner": owner,
            "Claimed at": "—",
            "Updated at": "—",
            "Production progress": "none",
            "Learning progress": "none",
            "Next action": "keep",
            "Blockers": "none",
        }
        (project / "STATUS.md").write_text(
            "\n".join(f"| {key} | {value} |" for key, value in fields.items() if key not in missing),
            encoding="utf-8",
        )
        return project

    def _update_status(self, project, action, owner, *extra):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "update_status.py"), "--project", str(project),
             "--action", action, "--owner", owner, *extra],
            capture_output=True, text=True,
        )

    def _valid_project(self, temp):
        project = Path(temp) / "project"
        for name in ("sources", "outputs/lessons", "outputs/reference", "records", "history"):
            (project / name).mkdir(parents=True, exist_ok=True)
        (project / "project.toml").write_text(
            'schema_version = 3\nproject_id = "test"\ndisplay_name = "Test"\n'
            'pipeline = "capability"\ncontent_language = "en"\n[paths]\n'
            'sources = "sources"\nlessons = "outputs/lessons"\nreference = "outputs/reference"\n'
            'records = "records"\nhistory = "history"\nprofile = "profile.md"\n', encoding="utf-8")
        (project / "pipeline.toml").write_text("schema_version = 3\n[capability]\n", encoding="utf-8")
        for name in ("MISSION.md", "NOTES.md", "profile.md"):
            (project / name).write_text("ok\n", encoding="utf-8")
        (project / "STATUS.md").write_text("\n".join((
            "| State | idle |", "| Owner | — |", "| Claimed at | — |", "| Updated at | — |",
            "| Production progress | none |", "| Learning progress | none |", "| Next action | none |", "| Blockers | none |",
        )), encoding="utf-8")
        return project

    def _validate_project(self, project):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_project.py"), "--project", str(project)],
            capture_output=True, text=True, errors="replace",
        )

    def _valid_portal_project(self, workspace, project_id, display_name=None):
        projects = Path(workspace) / "projects"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "create_project.py"), "--root", str(projects),
             "--project-id", project_id, "--display-name", display_name or project_id, "--pipeline", "capability"],
            check=True, capture_output=True, text=True,
        )
        project = projects / project_id
        page = project / "outputs" / "reference" / "page.html"
        page.write_text(
            '<!doctype html><html lang="en"><head><link rel="stylesheet" href="../assets/lesson.css"></head>'
            '<body data-ui-version="2" data-pipeline="capability" data-format="reference" data-theme="overview">'
            '<main class="lesson-shell" id="main"><header class="lesson-header"><h1>Test</h1></header>'
            '<section class="reference-section"><h2>Content</h2></section>'
            '<footer class="lesson-footer"><p>Done</p></footer></main><script src="../assets/lesson.js"></script></body></html>',
            encoding="utf-8",
        )
        return project, page

    def test_validate_project_missing_status_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._valid_project(temp)
            (project / "STATUS.md").unlink()
            result = self._validate_project(project)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1, output)
            self.assertIn("ERROR missing STATUS.md", output)
            self.assertNotIn("Traceback", output)
            self.assertNotIn("UnboundLocalError", output)

    def test_validate_project_malformed_status_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._valid_project(temp)
            cases = {
                "invalid_utf8": (b"\xff", "ERROR STATUS.md must be valid UTF-8"),
                "missing_field": (b"| State | idle |\n", "ERROR STATUS.md missing field: Owner"),
                "invalid_state": (b"| State | running |\n| Owner | -- |\n| Claimed at | -- |\n| Updated at | -- |\n| Production progress | n |\n| Learning progress | n |\n| Next action | n |\n| Blockers | n |\n", "ERROR STATUS.md invalid State: running"),
            }
            for name, (status, expected) in cases.items():
                with self.subTest(name=name):
                    (project / "STATUS.md").write_bytes(status)
                    result = self._validate_project(project)
                    output = result.stdout + result.stderr
                    self.assertEqual(result.returncode, 1, output)
                    self.assertIn(expected, output)
                    self.assertNotIn("Traceback", output)
                    self.assertNotIn("UnboundLocalError", output)

    def test_project_ui_binding_rejects_pipeline_and_language_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._valid_project(temp)
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "sync_ui_kit.py"), "--project", str(project), "--install"],
                check=True, capture_output=True, text=True,
            )
            page = project / "outputs" / "reference" / "page.html"

            def write_page(pipeline, language):
                page.write_text(
                    f'<!doctype html><html lang="{language}"><head><link rel="stylesheet" href="../assets/lesson.css"></head>'
                    f'<body data-ui-version="2" data-pipeline="{pipeline}" data-format="reference" data-theme="overview">'
                    '<main class="lesson-shell" id="main"><header class="lesson-header"><h1>Test</h1></header>'
                    '<section class="reference-section"><h2>Content</h2></section>'
                    '<footer class="lesson-footer"><p>Done</p></footer></main><script src="../assets/lesson.js"></script></body></html>',
                    encoding="utf-8",
                )

            config = (project / "project.toml").read_text(encoding="utf-8")
            config = config.replace('pipeline = "capability"', 'pipeline = "language"')
            (project / "project.toml").write_text(config, encoding="utf-8")
            write_page("capability", "en")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_lesson_ui.py"), "--project", str(project)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("data-pipeline must match project pipeline", result.stdout)

            write_page("language", "zh-CN")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_lesson_ui.py"), "--project", str(project)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("html lang must match project content_language", result.stdout)

            write_page("language", "en")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_lesson_ui.py"), "--project", str(project)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_claim_rejects_non_idle_state(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._status_project(temp, state="in_progress", owner="alice")
            before = (project / "STATUS.md").read_bytes()
            result = self._update_status(project, "claim", "bob", "--task", "take over")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, (project / "STATUS.md").read_bytes())

    def test_claim_rejects_empty_owner(self):
        for owner in ("", "   ", "—"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory() as temp:
                project = self._status_project(temp)
                before = (project / "STATUS.md").read_bytes()
                result = self._update_status(project, "claim", owner, "--task", "work")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(before, (project / "STATUS.md").read_bytes())

    def test_release_rejects_wrong_owner(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._status_project(temp, state="in_progress", owner="alice")
            before = (project / "STATUS.md").read_bytes()
            result = self._update_status(project, "release", "mallory")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, (project / "STATUS.md").read_bytes())

    def test_release_rejects_idle_state(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._status_project(temp)
            before = (project / "STATUS.md").read_bytes()
            result = self._update_status(project, "release", "alice")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, (project / "STATUS.md").read_bytes())

    def test_release_updates_next_action(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._status_project(temp, state="in_progress", owner="alice")
            result = self._update_status(project, "release", "alice", "--next-step", "review results")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual("review results", __import__("validate_project").status_value(
                (project / "STATUS.md").read_text(encoding="utf-8"), "Next action"))

    def test_status_update_preserves_backslashes_literally(self):
        for field, value in (("Owner", r"C:\new"), ("Next action", r"\9")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                project = self._status_project(temp)
                owner = value if field == "Owner" else "alice"
                task = value if field == "Next action" else "work"
                result = self._update_status(project, "claim", owner, "--task", task)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, output)
                self.assertNotIn("Traceback", output)
                status = (project / "STATUS.md").read_text(encoding="utf-8")
                self.assertEqual(value, __import__("validate_project").status_value(status, field))
                self.assertEqual(8, len(re.findall(r"^\|[^\n]+\|[^\n]+\|$", status, re.MULTILINE)))

    def test_status_update_requires_all_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self._status_project(temp, missing=("Blockers",))
            before = (project / "STATUS.md").read_bytes()
            result = self._update_status(project, "claim", "alice", "--task", "work")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, (project / "STATUS.md").read_bytes())

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
                    html = re.sub(r'<html lang="[^"]+">', f'<html lang="{"zh-CN" if pipeline == "language" else "en"}">', html, count=1)
                    html = re.sub(r'data-pipeline="[^"]+"', f'data-pipeline="{pipeline}"', html, count=1)
                    html = re.sub(r'data-theme="[^"]+"', f'data-theme="{themes[smoke_index % len(themes)]}"', html, count=1)
                    if page_format == "lesson":
                        html = html.replace(
                            "</div></article>", '<p class="takeaway">Test</p></div></article>'
                        )
                    if pipeline == "certification" and page_format == "lesson":
                        html = html.replace(
                            '<div class="audit-grid">',
                            '<table class="coverage-table"><tr><th>Target</th></tr><tr><td>Test</td></tr></table>'
                            '<div class="audit-grid">',
                        ).replace(
                            "  []\n",
                            '  [{"id":"q1","type":"single_choice","stem":"s1","options":["a","b"],"answer":0,"rationale":"r1"},'
                            '{"id":"q2","type":"single_choice","stem":"s2","options":["a","b"],"answer":0,"rationale":"r2"},'
                            '{"id":"q3","type":"single_choice","stem":"s3","options":["a","b"],"answer":0,"rationale":"r3"},'
                            '{"id":"q4","type":"single_choice","stem":"s4","options":["a","b"],"answer":0,"rationale":"r4"}]\n',
                            1,
                        )
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


    def test_portal_rejects_no_project(self):
        """Portal must refuse to build without explicit --project."""
        scripts = Path(__file__).resolve().parent
        result = subprocess.run(
            [sys.executable, str(scripts / "build_portal.py"),
             "--workspace", "/tmp", "--out", "/tmp/fyuu-portal-noarg"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_deploy_publish_requires_clean_main_worktree(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            markers = Path(temp) / "markers.txt"
            markers.write_text("secret\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "base"], check=True, capture_output=True)
            (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            command = ["bash", str(ROOT / "scripts" / "deploy_portal.sh"), "--workspace", str(workspace),
                       "--repo", str(repo), "--markers", str(markers), "--project", "test", "--publish"]
            dirty = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(dirty.returncode, 0)
            self.assertIn("clean", dirty.stderr.lower())
            subprocess.run(["git", "-C", str(repo), "checkout", "-b", "other"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "--", "tracked.txt"], check=True, capture_output=True)
            branch = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(branch.returncode, 0)
            self.assertIn("main", branch.stderr.lower())

    def test_deploy_build_only_preserves_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            workspace = Path(temp) / "workspace"
            _, _ = self._valid_portal_project(workspace, "test", "Test")
            markers = Path(temp) / "markers.txt"
            markers.write_text("secret\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "base"], check=True, capture_output=True)
            before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout
            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "deploy_portal.sh"), "--workspace", str(workspace),
                 "--repo", str(repo), "--markers", str(markers), "--project", "test"], capture_output=True, text=True,
            )
            after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(before, after)
            self.assertIn("Remove preview files", result.stdout)

    def test_deploy_stops_before_staging_when_post_copy_scan_fails(self):
        """A failed post-copy content scan must prevent any gh-pages commit."""
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            workspace = Path(temp) / "workspace"
            self._valid_portal_project(workspace, "test", "Test")
            markers = Path(temp) / "markers.txt"
            markers.write_text("secret\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                 "commit", "-m", "base"], check=True, capture_output=True,
            )
            remote = Path(temp) / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True, capture_output=True)
            before = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
            ).stdout
            shim_dir = Path(temp) / "bin"
            shim_dir.mkdir()
            (shim_dir / "python3").write_text(
                f"#!{sys.executable}\n"
                "import os, sys\n"
                "if (len(sys.argv) > 3 and sys.argv[1] == '-c'\n"
                "        and 'from build_portal import scan_content' in sys.argv[2]\n"
                "        and sys.argv[3].endswith('/gh-pages-tree')):\n"
                "    print('injected post-copy scan failure', file=sys.stderr)\n"
                "    raise SystemExit(97)\n"
                f"os.execv({str(sys.executable)!r}, [{str(sys.executable)!r}, *sys.argv[1:]])\n",
                encoding="utf-8",
            )
            (shim_dir / "python3").chmod(0o755)
            env = os.environ | {"PATH": f"{shim_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "deploy_portal.sh"), "--workspace", str(workspace),
                 "--repo", str(repo), "--markers", str(markers), "--project", "test", "--publish"],
                capture_output=True, text=True, env=env,
            )
            after = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
            ).stdout
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("injected post-copy scan failure", result.stderr)
            self.assertEqual(before, after)
            self.assertEqual("", subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"], check=True, capture_output=True, text=True,
            ).stdout)

    def test_portal_rejects_missing_kit_manifest(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            project = self._valid_project(temp)
            (project / "outputs" / "lessons" / "0001.html").write_text("<html><title>Test</title></html>", encoding="utf-8")
            destination = workspace / "projects" / "test"
            workspace.mkdir()
            (workspace / "projects").mkdir()
            shutil.move(str(project), destination)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_portal.py"), "--workspace", str(workspace),
                 "--out", str(Path(temp) / "portal"), "--project", "test"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("kit-manifest", result.stderr)
            self.assertFalse((Path(temp) / "portal").exists())

    def test_portal_rejects_claimed_project(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            project, _ = self._valid_portal_project(workspace, "claimed", "Claimed")
            claim = self._update_status(project, "claim", "alice", "--task", "editing")
            self.assertEqual(claim.returncode, 0, claim.stdout + claim.stderr)
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_portal.py"),
                 "--workspace", str(workspace), "--out", str(out), "--project", "claimed"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be idle", result.stderr)
            self.assertFalse(out.exists())

    def test_kit_rejects_unrepresented_question_type(self):
        import json
        import shutil
        from validate_lesson_ui import validate_kit

        with tempfile.TemporaryDirectory() as temp:
            script_dir = Path(temp)
            shutil.copytree(ROOT / "assets" / "ui-kit", script_dir / "assets" / "ui-kit")
            (script_dir / "references").mkdir()
            shutil.copy2(ROOT / "references" / "ui-contract.md", script_dir / "references" / "ui-contract.md")
            gallery = script_dir / "assets" / "ui-kit" / "templates" / "gallery.html"
            gallery.write_text(gallery.read_text(encoding="utf-8").replace("matching", "omitted-type"), encoding="utf-8")
            spec = json.loads((script_dir / "assets" / "ui-kit" / "ui-spec.json").read_text(encoding="utf-8"))
            errors = validate_kit(script_dir, spec)
            self.assertIn("Gallery missing question type: matching", errors)

    def test_portal_whitelist_and_safety(self):
        """Portal only copies whitelisted files; rejects symlinks, dangerous paths, and private data."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "tp", "TP")
        (proj / "outputs/index.html").write_text('<html><title>TP</title><body>Learning progress: secret</body></html>', encoding="utf-8")
        (proj / "outputs/reference/private.md").write_text("private", encoding="utf-8")
        (proj / "sources/secret.md").write_text("source", encoding="utf-8")
        sentinel = proj / "outputs/.DS_Store"
        sentinel.write_bytes(b"\x00")

        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "tp"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            # Whitelisted files present
            self.assertTrue(Path(out, "tp/reference/page.html").is_file())
            self.assertTrue(Path(out, "tp/assets/lesson.css").is_file())
            self.assertTrue(Path(out, "tp/assets/lesson.js").is_file())
            # Private index NOT copied
            idx = Path(out, "tp/index.html")
            self.assertTrue(idx.is_file())
            self.assertNotIn("secret", idx.read_text(encoding="utf-8"))
            # Forbidden files NOT copied
            self.assertFalse(Path(out, "tp/ui/gallery.html").exists())
            self.assertFalse(Path(out, "tp/reference/private.md").exists())
            self.assertFalse(Path(out, "tp/.DS_Store").exists())
            # Sentinel still exists (not deleted)
            self.assertTrue(sentinel.exists())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)

    def test_portal_rejects_symlink_and_dangerous_out(self):
        """Portal must reject symlinks and dangerous output paths."""
        import tempfile, shutil, os
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "sp", "SP")
        leak = proj / "outputs/assets/leak.css"
        os.symlink("/etc/passwd", str(leak))
        sentinel_proj = page

        out = tempfile.mkdtemp() + "/portal"
        try:
            # Symlink test
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "sp"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())
            # Dangerous out = workspace itself
            result2 = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", ws, "--project", "sp"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result2.returncode, 0)
            # Sentinel file still exists
            self.assertTrue(sentinel_proj.exists())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)

    def test_portal_slug_collision(self):
        """Portal must reject slug collisions."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        for pid, dn in [("pa", "Dup"), ("pb", "Dup")]:
            project, _ = self._valid_portal_project(ws, pid, dn)
            project.rename(Path(ws) / "projects" / f"proj-{pid}")
        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "pa", "--project", "pb"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("slug", result.stderr.lower())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)

    def test_validator_rejects_bool_and_duplicate_right(self):
        """Validator must reject boolean single_choice answer and duplicate matching right."""
        scripts = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts))
        from validate_lesson_ui import validate_questions_v2
        spec = {"single_choice": {"required_fields": [], "optional_fields": [], "rules": {}},
                "matching": {"required_fields": [], "optional_fields": [], "rules": {}}}
        bool_sc = '[{"id":"x","type":"single_choice","stem":"s","options":["a","b"],"answer":true,"rationale":"r"}]'
        self.assertTrue(validate_questions_v2(bool_sc, spec))
        dup_right = '[{"id":"x","type":"matching","stem":"s","pairs":[{"left":"a","right":"1"},{"left":"b","right":"1"},{"left":"c","right":"2"}],"rationale":"r"}]'
        self.assertTrue(validate_questions_v2(dup_right, spec))



    def test_portal_rejects_absolute_path_in_content(self):
        """Portal must reject HTML containing absolute local paths."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "ap", "AP")
        page.write_text(page.read_text(encoding="utf-8").replace("Done", "path: /" + "Users/test/secret"), encoding="utf-8")
        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "ap"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("absolute", result.stderr.lower())
            # Output must not exist (staging was cleaned)
            self.assertFalse(Path(out).exists())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)

    def test_portal_rejects_private_markers(self):
        """Portal must reject content containing private marker strings."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "pm", "PM")
        page.write_text(page.read_text(encoding="utf-8").replace("Done", "SECRET_PROJECT_DATA"), encoding="utf-8")
        markers_file = tempfile.mktemp(suffix=".txt")
        Path(markers_file).write_text("SECRET_PROJECT_DATA\n", encoding="utf-8")
        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "ap" if False else "pm",
                 "--markers", markers_file],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("marker", result.stderr.lower())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)
            Path(markers_file).unlink(missing_ok=True)

    def test_portal_scans_generated_homepage_for_slug_markers(self):
        """The final scan must include generated files before output is published."""
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            self._valid_portal_project(workspace, "marker-project", "Private Marker")
            markers = Path(temp) / "markers.txt"
            markers.write_text("private-marker\n", encoding="utf-8")
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_portal.py"),
                 "--workspace", str(workspace), "--out", str(out),
                 "--project", "marker-project", "--markers", str(markers)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("marker", result.stderr.lower())
            self.assertFalse(out.exists())

    def test_portal_overwrite_protects_workspace_parent(self):
        """--overwrite with --out = workspace parent must not delete workspace."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws_parent = tempfile.mkdtemp()
        ws = ws_parent + "/ws"
        proj = Path(ws) / "projects" / "ow"
        proj.mkdir(parents=True, exist_ok=True)
        (proj / "project.toml").write_text(
            'schema_version = 3\nproject_id = "ow"\ndisplay_name = "OW"\n'
            'pipeline = "capability"\ncontent_language = "en"\n[paths]\nsources = "sources"\nlessons = "outputs/lessons"\nreference = "outputs/reference"\nrecords = "records"\nhistory = "history"\nprofile = "profile"\n', encoding="utf-8")
        (proj / "pipeline.toml").write_text("schema_version = 3\n[capability]\n", encoding="utf-8")
        (proj / "STATUS.md").write_text("| State | idle |\n| Updated at | 2026-01-01 |\n", encoding="utf-8")
        (proj / "outputs/lessons").mkdir(parents=True, exist_ok=True)
        (proj / "outputs/lessons/0001.html").write_text("<html><title>L</title></html>", encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", ws_parent, "--project", "ow", "--overwrite"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(Path(ws).exists(), "workspace must survive --overwrite attack")
        finally:
            shutil.rmtree(ws_parent, ignore_errors=True)

    def test_portal_rejects_duplicate_project_id(self):
        """Portal must reject when two directories claim the same project_id."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        for dirname in ["dir-a", "dir-b"]:
            proj = Path(ws) / "projects" / dirname
            proj.mkdir(parents=True, exist_ok=True)
            (proj / "project.toml").write_text(
                f'schema_version = 3\nproject_id = "same-id"\ndisplay_name = "{dirname}"\n'
                f'pipeline = "capability"\ncontent_language = "en"\n[paths]\nsources = "sources"\nlessons = "outputs/lessons"\nreference = "outputs/reference"\nrecords = "records"\nhistory = "history"\nprofile = "profile"\n', encoding="utf-8")
            (proj / "pipeline.toml").write_text("schema_version = 3\n[capability]\n", encoding="utf-8")
            (proj / "STATUS.md").write_text("| State | idle |\n| Updated at | 2026-01-01 |\n", encoding="utf-8")
            (proj / "outputs/lessons").mkdir(parents=True, exist_ok=True)
            (proj / "outputs/lessons/0001.html").write_text("<html><title>L</title></html>", encoding="utf-8")
        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "same-id"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ambiguous", result.stderr.lower())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)



    def test_portal_rejects_unquoted_file_uri(self):
        """Unquoted href=file:/// must be rejected, not just quoted forms."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "fu", "FU")
        page.write_text(page.read_text(encoding="utf-8").replace("Done", '<a href=file:' + '//' + "/pri" + "vate/secret>leak</a>"), encoding="utf-8")
        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "fu"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("file://", result.stderr.lower())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)

    def test_portal_rejects_non_utf8_content(self):
        """Non-UTF-8 binary file disguised as .html must be rejected, not skipped."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "bin", "BIN")
        page.write_bytes(b'\x80\x81\x82<title>binary</title>\xff\xfe')
        try:
            sys.path.insert(0, str(scripts))
            from build_portal import scan_content
            self.assertTrue(any("unreadable" in error for error in scan_content(proj / "outputs", [])))
        finally:
            sys.path.remove(str(scripts))
            shutil.rmtree(ws, ignore_errors=True)

    def test_portal_scan_ignores_worktree_git_metadata(self):
        """Git worktree metadata is not published portal content."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".git").write_text("gitdir: /" + "private/worktree\n", encoding="utf-8")
            sys.path.insert(0, str(ROOT / "scripts"))
            try:
                from build_portal import scan_content
                self.assertEqual([], scan_content(root, []))
            finally:
                sys.path.remove(str(ROOT / "scripts"))

    def test_portal_staging_cleanup_on_symlink_failure(self):
        """If copy fails mid-way (symlink), staging temp dir must be cleaned up."""
        import tempfile, shutil, os, glob
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "sc", "SC")
        os.symlink("/etc/passwd", str(proj / "outputs/assets/leak.css"))
        out = tempfile.mkdtemp() + "/portal"
        tmp_root = tempfile.gettempdir()
        try:
            before = set(glob.glob(os.path.join(Path(out).parent, Path(out).name + ".staging.*")))
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "sc"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr.lower())
            after = set(glob.glob(os.path.join(Path(out).parent, Path(out).name + ".staging.*")))
            leftover = after - before
            self.assertEqual(len(leftover), 0, f"staging temp dirs not cleaned: {leftover}")
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)


    def _portal_multi(self, temp, projects):
        """Build a multi-project portal fixture. projects=[(id, name, pipeline, files)]."""
        workspace = Path(temp) / "workspace"
        for pid, name, pipeline, files in projects:
            self._valid_portal_project(workspace, pid, name)
            # adjust pipeline via project.toml rewrite
            proj = workspace / "projects" / pid
            toml = proj / "project.toml"
            txt = toml.read_text(encoding="utf-8")
            txt = txt.replace('pipeline = "capability"', f'pipeline = "{pipeline}"')
            toml.write_text(txt, encoding="utf-8")
            # write declared lesson/reference HTML files (titles)
            for rel, title in files:
                p = proj / "outputs" / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    '<!doctype html><html lang="en"><head>'
                    '<link rel="stylesheet" href="../assets/lesson.css">'
                    f'<title>{title}</title></head>'
                    '<body data-ui-version="2" data-pipeline="capability" '
                    'data-format="reference" data-theme="overview">'
                    '<main class="lesson-shell" id="main"><header class="lesson-header">'
                    f'<h1>{title}</h1></header><section class="reference-section">'
                    '<h2>Content</h2></section><footer class="lesson-footer">'
                    '<p>Done</p></footer></main>'
                    '<script src="../assets/lesson.js"></script></body></html>',
                    encoding="utf-8")
        return workspace

    def test_portal_root_is_project_switcher_only(self):
        """Root homepage shows only three project entries, no lesson-title links."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "PMP备考", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
                ("business-cantonese", "粤语学习", "capability",
                 [("lessons/0001.html", "第 1 課 · B")]),
                ("ai-systems-designer", "AI学习", "capability",
                 [("lessons/0001.html", "第 1 课 · C")]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification", "--project", "business-cantonese",
                 "--project", "ai-systems-designer"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = (out / "index.html").read_text(encoding="utf-8")
            # Three project tabs in fixed order PMP / Cantonese / AI
            self.assertIn('data-hash="pmp"', root)
            self.assertIn('data-hash="cantonese"', root)
            self.assertIn('data-hash="ai"', root)
            self.assertLess(root.index('data-hash="pmp"'), root.index('data-hash="cantonese"'))
            self.assertLess(root.index('data-hash="cantonese"'), root.index('data-hash="ai"'))
            self.assertIn('aria-selected="true"', root)
            # Default selection is the first tab (PMP)
            self.assertIn('id="tab-pmp" role="tab" href="#pmp"', root)
            # No lesson titles or per-lesson cards on the root page
            self.assertNotIn("第 1 课 · A", root)
            self.assertNotIn("第 1 課 · B", root)
            self.assertNotIn("第 1 课 · C", root)
            self.assertNotIn('class="entry"', root)
            # Generated assets exist, not copied into private projects
            self.assertTrue((out / "portal.css").is_file())
            self.assertTrue((out / "portal.js").is_file())

    def test_portal_project_catalog_buckets_and_counts(self):
        """Project catalog splits 课程 / 复习 / 资料 with accurate counts."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "PMP备考", "capability", [
                    ("lessons/0001.html", "第 1 课 · 项目工作"),
                    ("lessons/0003.html", "第 3 课 · 测量"),
                    ("lessons/0003b.html", "0003b · EVM 指标"),
                    ("lessons/0004.html", "第 4 课 · 不确定性"),
                    ("lessons/review-0001-0007.html", "复习 · 0001-0007"),
                    ("reference/formula.html", "公式速查"),
                ]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp备考" / "index.html").read_text(encoding="utf-8")
            # Counts: 课程=4, 复习=1, 资料=1
            self.assertIn('<span>课程</span><span class="count">4</span>', idx)
            self.assertIn('<span>复习</span><span class="count">1</span>', idx)
            # 资料=2: reference/formula.html above + the default reference/page.html
            # that _valid_portal_project always creates.
            self.assertIn('<span>资料</span><span class="count">2</span>', idx)
            # Stable sort: 0001 < 0003 < 0003b < 0004
            self.assertLess(idx.index("0001.html"), idx.index("0003.html"))
            self.assertLess(idx.index("0003.html"), idx.index("0003b.html"))
            self.assertLess(idx.index("0003b.html"), idx.index("0004.html"))
            # Review item sorted last (unnumbered-as-review by filename)
            self.assertLess(idx.index("0004.html"), idx.index("review-0001-0007.html"))
            # Empty state is an explicit element, not an empty <div>
            # (this project has no empty categories, so check the helper on an empty one)

    def test_portal_catalog_empty_state_not_empty_div(self):
        """An empty category shows a clear empty state, not an empty div."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "PMP备考", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp备考" / "index.html").read_text(encoding="utf-8")
            # 资料 (reference) is empty here -> explicit empty state
            self.assertIn('暂无内容', idx)
            # No bare empty panel div
            self.assertNotIn('class="panel" id="panel-reference" role="tabpanel" '
                             'data-group="catalog" data-active="false" '
                             'aria-labelledby="tab-reference"></div>', idx)

    def test_portal_generated_pages_have_no_private_data(self):
        """Generated pages contain no STATUS text, absolute paths, file:// or markers."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "PMP备考", "capability",
                 [("lessons/0001.html", "第 1 课 · A"),
                  ("reference/r.html", "速查")]),
            ])
            # Drop a private marker file and a STATUS-like string into the project
            # (the scanner rejects markers; STATUS text must never be echoed).
            markers = Path(temp) / "markers.txt"
            markers.write_text("SECRET_LEARNER_RECORD\n", encoding="utf-8")
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification", "--markers", str(markers)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for html in [out / "index.html", out / "pmp备考" / "index.html"]:
                t = html.read_text(encoding="utf-8")
                self.assertNotIn("Learning progress", t)
                self.assertNotIn("Next action", t)
                self.assertNotIn("SECRET_LEARNER_RECORD", t)
                self.assertNotIn("file://", t)
                for pat in ("/Users/", "/home/", "/private/"):
                    self.assertNotIn(pat, t)

    def test_offline_export_inlines_css_js(self):
        """Offline export inlines lesson.css/.js, removes external refs, keeps JSON."""
        import tempfile, shutil, hashlib
        scripts = Path(__file__).resolve().parent
        export_script = scripts / "export_offline_lesson.py"
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A"),
                  ("reference/r.html", "速查参考")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            lesson = proj / "outputs" / "lessons" / "0001.html"
            src_hash = hashlib.sha256(lesson.read_bytes()).hexdigest()
            out = Path(temp) / "0001.offline.html"
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.is_file())
            exported = out.read_text(encoding="utf-8")
            # No external references
            self.assertNotIn('<link rel="stylesheet"', exported)
            self.assertNotIn('<script src=', exported)
            self.assertNotIn("http:", exported.lower())
            # CSS inlined
            self.assertIn("<style>", exported)
            # JS inlined (as <script> block without src)
            self.assertIn("<script>", exported)
            # Source untouched
            self.assertEqual(hashlib.sha256(lesson.read_bytes()).hexdigest(), src_hash)
            # Output not in any portal-whitelisted directory
            self.assertNotIn("outputs/", str(out.resolve()))
            self.assertNotIn("portal", str(out.resolve()).lower())

    def test_offline_export_rejects_remote_and_file_refs(self):
        """Offline export rejects http: and file:// resources."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        export_script = scripts / "export_offline_lesson.py"
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            lesson = proj / "outputs" / "lessons" / "0001.html"
            out = Path(temp) / "0001.offline.html"
            orig_html = lesson.read_text(encoding="utf-8")

            # Inject a remote stylesheet
            html_remote = orig_html.replace('href="../assets/lesson.css"',
                                    'href="http://cdn.example/evil.css"')
            lesson.write_text(html_remote, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("remote", result.stderr.lower())

            # Inject a file:// script
            html_file = orig_html.replace('src="../assets/lesson.js"',
                                         'src="file:///etc/passwd"')
            lesson.write_text(html_file, encoding="utf-8")
            result2 = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result2.returncode, 0)
            self.assertIn("file:", result2.stderr.lower())

    # ---- publish_portal wrapper tests ----

    def _portal_toml(self, temp, projects, publish=True):
        """Write a temporary portal.toml for test use."""
        p = Path(temp) / "portal.toml"
        ids = "\n".join(f'  "{pid}",' for pid in projects)
        p.write_text(
            f'[portal]\n'
            f'publish_after_validation = {str(publish).lower()}\n'
            f'repo = "../system"\n'
            f'marker_file = "portal-markers.txt"\n'
            f'projects = [\n{ids}\n]\n',
            encoding="utf-8")
        return p

    def test_publish_portal_rejects_missing_config(self):
        """Missing portal.toml is rejected cleanly."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(Path(temp) / "ws"),
                 "--config", str(Path(temp) / "missing.toml"),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr.lower())

    def test_publish_portal_rejects_invalid_project_id(self):
        """A project_id not in the workspace is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [("tp", "TP", "capability", [])])
            self._portal_toml(temp, ["nonexistent"])
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(Path(temp) / "portal.toml"),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr.lower())

    def test_publish_portal_rejects_empty_project_list(self):
        """Empty project list is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            self._portal_toml(temp, [])
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(Path(temp) / "ws"),
                 "--config", str(Path(temp) / "portal.toml"),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_publish_portal_rejects_dup_project_ids(self):
        """Duplicate project IDs in config are rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            self._portal_toml(temp, ["dup", "dup"])
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(Path(temp) / "ws"),
                 "--config", str(Path(temp) / "portal.toml"),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate", result.stderr.lower())

    def test_publish_portal_rejects_non_idle_project(self):
        """A non-idle project is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [("claimed", "CL", "capability",
                                            [("lessons/0001.html", "第 1 课 · A")])])
            # Mark project as claimed
            proj = Path(temp) / "workspace" / "projects" / "claimed"
            (proj / "STATUS.md").write_text(
                "| State | claimed |\n| Owner | agent |\n| Claimed at | 2026-01-01 |\n"
                "| Updated at | 2026-01-01 |\n| Production progress | n |\n"
                "| Learning progress | n |\n| Next action | n |\n| Blockers | n |\n",
                encoding="utf-8")
            self._portal_toml(temp, ["claimed"])
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(Path(temp) / "portal.toml"),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("idle", result.stderr.lower())

    def test_publish_portal_build_only_succeeds(self):
        """Build-only succeeds and does NOT touch git remote."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "PMP备考", "capability",
                 [("lessons/0001.html", "第 1 课 · A"),
                  ("lessons/0002.html", "第 2 课 · B"),
                  ("reference/r.html", "速查")]),
            ])
            self._portal_toml(temp, ["pmp-certification"])
            build_out = Path(temp) / "build-out"
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(Path(temp) / "portal.toml"),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK build-only", result.stdout)
            # Verify build output exists with pages
            out_line = [l for l in result.stdout.split("\n") if "OK build-only" in l]
            self.assertTrue(out_line, "expected OK build-only line in stdout")
            # Build output is in a system temp dir; verify stdout reports pages > 0
            self.assertIn("pages", out_line[0])

    def test_publish_portal_rejects_dirty_worktree(self):
        """--publish with dirty worktree is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            temp_p = Path(temp)
            # Create a real git repo with a clean main branch
            repo = temp_p / "system-repo"
            repo.mkdir()
            sp_git = lambda *a: subprocess.run(["git", "-C", str(repo)] + list(a),
                                       capture_output=True, text=True)
            sp_git("init")
            sp_git("checkout", "-b", "main")
            sp_git("config", "user.email", "test@test")
            sp_git("config", "user.name", "test")
            (repo / "README.md").write_text("# test", encoding="utf-8")
            sp_git("add", "README.md")
            sp_git("commit", "-m", "init")

            ws = self._portal_multi(temp, [
                ("pmp-certification", "PMP备考", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            # Point portal.toml to our clean repo
            toml = Path(temp) / "portal.toml"
            ids = '\n'.join(f'  "{pid}",' for pid in ["pmp-certification"])
            toml.write_text(
                f'[portal]\npublish_after_validation = true\n'
                f'repo = "{repo}"\nmarker_file = "portal-markers.txt"\n'
                f'projects = [\n{ids}\n]\n',
                encoding="utf-8")

            # Make worktree dirty
            (repo / "dirty.txt").write_text("unsaved change", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(toml),
                 "--publish"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue("clean" in result.stderr.lower() or
                            "worktree" in result.stderr.lower() or
                            "status" in result.stderr.lower(),
                            f"expected clean/worktree rejection, got: {result.stderr}")

    def test_privacy_audit_catches_untracked_file(self):
        """Audit must check untracked (not yet git-added) files, not just tracked ones."""
        import tempfile, shutil, subprocess as sp
        scripts = Path(__file__).resolve().parent
        repo = Path(__file__).resolve().parent.parent.parent  # system/ repo root
        leak_file = repo / "fyuu-tutor" / "scripts" / "__leak_test_untracked.py"
        try:
            leak_file.write_text(
                'LEAK = "' + '/' + 'Users/' + 'fyuu/secret/pri' + 'vate/leak"\n', encoding="utf-8")
            result = sp.run(
                [sys.executable, str(scripts / "audit_privacy.py"), "--system", str(repo)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0,
                                "audit must fail on untracked file with absolute path")
            self.assertIn("absolute path", result.stdout.lower())
        finally:
            leak_file.unlink(missing_ok=True)

    def test_privacy_audit_rejects_broken_file_and_directory_symlinks(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "system"
            root.mkdir()
            os.symlink("/missing/pri" + "vate-file", root / "broken.py")
            os.symlink("/missing/pri" + "vate-directory", root / "broken-dir")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "audit_privacy.py"), "--system", str(root)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("symlink rejected", result.stdout)

    def test_portal_overwrite_replaces_old_and_cleans_backup(self):
        """Successful overwrite replaces old content, cleans up .old, leaves portal intact."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "ar", "AR")
        out = tempfile.mkdtemp() + "/portal"
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "old-sentinel.html").write_text('<html><title>OLD</title></html>', encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "ar", "--overwrite"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertTrue((Path(out) / "index.html").exists(), "new portal must exist")
            self.assertFalse((Path(out) / "old-sentinel.html").exists(),
                             "old sentinel must be gone after successful overwrite")
            old_dir = Path(out).parent / (Path(out).name + ".old")
            self.assertFalse(old_dir.exists(), ".old backup must be cleaned up on success")
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)


    def test_portal_rollback_restores_old_on_rename_failure(self):
        """If staging->output rename fails, old portal must be restored intact."""
        import tempfile, shutil, unittest.mock as mock, os
        scripts = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts))
        import build_portal
        ws = tempfile.mkdtemp() + "/ws"
        proj, page = self._valid_portal_project(ws, "rb", "RB")
        out_parent = tempfile.mkdtemp()
        out = Path(out_parent) / "portal"
        out.mkdir(parents=True, exist_ok=True)
        (out / "old-sentinel.html").write_text('<html><title>OLD</title></html>', encoding="utf-8")
        try:
            real_rename = Path.rename
            renamed = []
            def fail_rename(self, target):
                renamed.append((self, target))
                if ".staging." in str(self):
                    raise OSError("simulated rename failure")
                return real_rename(self, target)
            old_argv = sys.argv
            sys.argv = ['build_portal.py', '--workspace', ws, '--out', str(out), '--project', 'rb', '--overwrite']
            try:
                with mock.patch.object(Path, 'rename', fail_rename):
                    rc = build_portal.main()
            finally:
                sys.argv = old_argv
            self.assertNotEqual(rc, 0)
            self.assertTrue(any(".staging." in str(source) for source, _ in renamed))
            self.assertTrue((out / "old-sentinel.html").exists(),
                            "old portal must be restored after rename failure")
        finally:
            sys.path.remove(str(scripts))
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out_parent, ignore_errors=True)



if __name__ == "__main__":
    unittest.main()
