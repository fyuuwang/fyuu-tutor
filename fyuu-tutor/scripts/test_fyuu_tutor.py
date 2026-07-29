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
            self.assertTrue(Path(out, "tp/ref-page.html").is_file())
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

    def test_portal_public_route_is_independent_of_display_name(self):
        """Localized display names never become public URL path segments."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        ws = tempfile.mkdtemp() + "/ws"
        project, _ = self._valid_portal_project(ws, "pmp-certification", "Exam Prep")
        out = tempfile.mkdtemp() + "/portal"
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", ws, "--out", out, "--project", "pmp-certification"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(Path(out, "pmp/index.html").is_file())
            self.assertFalse(Path(out, "Exam Prep").exists())
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            shutil.rmtree(out, ignore_errors=True)

    def test_portal_rejects_non_ascii_public_filename(self):
        """A localized filename cannot silently create a localized public URL."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [
                    ("lessons/0001-中文.html", "第 1 课"),
                ]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lowercase ascii", result.stderr.lower())

    def test_portal_flattens_pages_and_rewrites_local_links(self):
        """Published copies use short routes while source-relative links still work."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [
                    ("lessons/0001.html", "第 1 课 · A"),
                    ("reference/guide.html", "速查"),
                ]),
            ])
            guide = ws / "projects" / "pmp-certification" / "outputs" / "reference" / "guide.html"
            guide.write_text(guide.read_text(encoding="utf-8").replace(
                "Done", '<a href="../lessons/0001.html">进入课程</a>'
                '<a href="page.html">更多资料</a>'), encoding="utf-8")
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lesson = (out / "pmp" / "0001.html").read_text(encoding="utf-8")
            reference = (out / "pmp" / "ref-guide.html").read_text(encoding="utf-8")
            index = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="assets/lesson.css"', lesson)
            self.assertIn('src="assets/lesson.js"', lesson)
            self.assertIn('href="0001.html"', reference)
            self.assertIn('href="ref-page.html"', reference)
            self.assertIn('href="ref-guide.html"', index)
            self.assertFalse((out / "pmp" / "lessons").exists())
            self.assertFalse((out / "pmp" / "reference").exists())

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
            self._valid_portal_project(workspace, "private-marker", "Private Marker")
            markers = Path(temp) / "markers.txt"
            markers.write_text("private-marker\n", encoding="utf-8")
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_portal.py"),
                 "--workspace", str(workspace), "--out", str(out),
                "--project", "private-marker", "--markers", str(markers)],
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

    def test_portal_root_has_direct_project_cards(self):
        """Root homepage links directly to projects, without a tab-and-CTA detour."""
        import tempfile, shutil
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
                ("business-cantonese", "Language Lab", "capability",
                 [("lessons/0001.html", "第 1 課 · B")]),
                ("ai-systems-designer", "Capability Lab", "capability",
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
            # Three project cards in fixed PMP / Cantonese / AI order.
            self.assertIn('href="pmp/index.html"', root)
            self.assertIn('href="cantonese/index.html"', root)
            self.assertIn('href="ai/index.html"', root)
            self.assertLess(root.index('href="pmp/index.html"'), root.index('href="cantonese/index.html"'))
            self.assertLess(root.index('href="cantonese/index.html"'), root.index('href="ai/index.html"'))
            self.assertNotIn('role="tablist"', root)
            self.assertNotIn('role="tabpanel"', root)
            # No lesson titles or per-lesson cards on the root page
            self.assertNotIn("第 1 课 · A", root)
            self.assertNotIn("第 1 課 · B", root)
            self.assertNotIn("第 1 课 · C", root)
            self.assertNotIn('class="entry"', root)
            # Generated assets exist, not copied into private projects
            self.assertTrue((out / "portal.css").is_file())
            self.assertTrue((out / "portal.js").is_file())

    def test_ui_templates_keep_global_returns_out_of_top_navigation(self):
        """All content formats use one two-link dock; top bars stay page-local."""
        templates = ROOT / "assets" / "ui-kit" / "templates"
        for name in ("lesson", "practice", "reference"):
            text = (templates / f"{name}.html").read_text(encoding="utf-8")
            self.assertEqual(text.count('class="course-return-dock"'), 1, name)
            self.assertEqual(text.count('class="course-home"'), 1, name)
            self.assertEqual(text.count('class="course-back"'), 1, name)
        lesson = (templates / "lesson.html").read_text(encoding="utf-8")
        top = lesson[lesson.index('<nav class="course-nav"'):lesson.index('</nav>\n    </nav>')]
        self.assertNotIn('course-home', top)
        self.assertNotIn('course-back', top)
        reference = (templates / "reference.html").read_text(encoding="utf-8")
        index = reference[reference.index('<nav class="section-index"'):reference.index('</nav>\n    <header')]
        self.assertNotIn('course-home', index)
        self.assertNotIn('course-back', index)

    def test_local_indexes_apply_navigation_by_page_depth(self):
        """The workspace shelf has no return; a project route has portal only."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "Lesson")]),
            ])
            project = ws / "projects" / "pmp-certification"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_index.py"), "--project", str(project)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            route = (project / "outputs" / "index.html").read_text(encoding="utf-8")
            shelf = (ws / "index.html").read_text(encoding="utf-8")
            self.assertEqual(route.count('class="course-return-dock"'), 1)
            self.assertIn('href="../../../index.html"', route)
            self.assertNotIn('course-back', route)
            self.assertNotIn('<nav class="course-return-dock"', shelf)

    def test_public_portal_navigation_depth_and_runtime_routes(self):
        """Root has no dock, project route has home, content pages get 2-link runtime paths."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "Lesson")]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = (out / "index.html").read_text(encoding="utf-8")
            route = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            lesson = (out / "pmp" / "0001.html").read_text(encoding="utf-8")
            self.assertNotIn('course-return-dock', root)
            self.assertEqual(route.count('class="course-return-dock"'), 1)
            self.assertIn('class="course-home"', route)
            self.assertNotIn('class="course-back"', route)
            self.assertIn('data-portal-home="../index.html"', lesson)
            self.assertIn('data-course-route="index.html"', lesson)

    def test_portal_project_catalog_buckets_and_counts(self):
        """Project catalog splits 课程 / 复习 / 资料 with accurate counts."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [
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
            idx = (out / "pmp" / "index.html").read_text(encoding="utf-8")
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

    def test_portal_catalog_hides_empty_categories(self):
        """A project route never shows empty review/reference destinations."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn('tab-review', idx)
            self.assertNotIn('panel-review', idx)
            self.assertNotIn('href="#review"', idx)
            self.assertNotIn('暂无内容', idx)
            self.assertIn('tab-lessons', idx)
            self.assertIn('tab-reference', idx)

    def test_portal_catalog_with_one_category_has_no_tab_semantics(self):
        """One populated category is a route list, never an orphaned tabpanel."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [("lessons/0001.html", "第 01 课 · A")]),
            ])
            (ws / "projects" / "pmp-certification" / "outputs" / "reference" / "page.html").unlink()
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out), "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            self.assertIn("课程路线", idx)
            self.assertNotIn('role="tablist"', idx)
            self.assertNotIn('role="tabpanel"', idx)

    def test_portal_catalog_manifest_groups_micro_lessons(self):
        """Optional public metadata turns A/B pages into one visible course package."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [
                    ("lessons/0001.html", "第 01 课 · Value"),
                    ("lessons/0002a.html", "第 02A 课 · Build vision"),
                    ("lessons/0002b.html", "第 02B 课 · Renew vision"),
                    ("lessons/0003.html", "第 03 课 · Stakeholders"),
                ]),
            ])
            manifest = ws / "projects" / "pmp-certification" / "outputs" / "catalog.json"
            manifest.write_text('''{"schema_version":1,"groups":[{"id":"0002","title":"Shared vision","parts":[{"id":"0002A","title":"Build vision","href":"0002a.html"},{"id":"0002B","title":"Renew vision","href":"0002b.html"}]}]}\n''', encoding="utf-8")
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out), "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            self.assertEqual(idx.count("Shared vision"), 1)
            self.assertLess(idx.index("0001.html"), idx.index("Shared vision"))
            self.assertLess(idx.index("Shared vision"), idx.index("0003.html"))
            self.assertLess(idx.index("0002a.html"), idx.index("0002b.html"))
            self.assertIn('href="0003.html"', idx)
            first = (out / "pmp" / "0001.html").read_text(encoding="utf-8")
            middle = (out / "pmp" / "0002a.html").read_text(encoding="utf-8")
            self.assertIn('data-portal-home="../index.html"', first)
            self.assertIn('data-portal-home', (out / "pmp" / "assets" / "lesson.js").read_text(encoding="utf-8"))
            self.assertIn('class="course-pagination"', first)
            self.assertIn('href="0002a.html"', first)
            self.assertIn('href="0001.html"', middle)
            self.assertIn('href="0002b.html"', middle)

    def test_portal_generated_pages_have_no_private_data(self):
        """Generated pages contain no STATUS text, absolute paths, file:// or markers."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
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
            for html in [out / "index.html", out / "pmp" / "index.html"]:
                t = html.read_text(encoding="utf-8")
                self.assertNotIn("Learning progress", t)
                self.assertNotIn("Next action", t)
                self.assertNotIn("SECRET_LEARNER_RECORD", t)
                self.assertNotIn("file://", t)
                for pat in ("/Users/", "/home/", "/private/"):
                    self.assertNotIn(pat, t)

    def test_portal_css_does_not_unconditionally_hide_panels(self):
        """Generated portal.css must not hide .panel without a JS-enable gate."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            css = (out / "portal.css").read_text(encoding="utf-8")
            # The old unconditional rule must be gone: no .panel hiding
            # unless preceded by the .js gate.  Use regex so the check is
            # not fooled by the new ".js .panel{display:none}" substring.
            import re
            bare = re.search(r'(?<!\.js )\.panel\{display:none\}', css)
            self.assertIsNone(bare,
                "unconditional .panel{display:none} still present in CSS")
            # Hiding must be gated behind a JS-enable selector on <html>.
            self.assertIn(".js .panel{display:none}", css)
            self.assertIn(".js .panel[data-active=\"true\"]{display:block}", css)

    def test_portal_js_adds_html_js_class(self):
        """portal.js must add the 'js' class to <html> so panel hiding engages."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            js = (out / "portal.js").read_text(encoding="utf-8")
            # The script must add the js class to the document root.
            self.assertIn("documentElement", js)
            self.assertIn("classList.add('js')", js)
            # It must do so early, before panel activation logic.
            self.assertLess(js.index("documentElement"),
                            js.index("function groups"))

    def test_portal_root_has_three_direct_cards_without_js(self):
        """Root portal has three direct project links and no JavaScript dependency."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
                ("business-cantonese", "Language Lab", "capability",
                 [("lessons/0001.html", "第 1 課 · B")]),
                ("ai-systems-designer", "AI系统设计", "capability",
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
            for href in ("pmp/index.html", "cantonese/index.html", "ai/index.html"):
                self.assertIn(f'href="{href}"', root)
            self.assertNotIn('role="tablist"', root)
            self.assertNotIn('class="js"', root)
            self.assertNotIn('class=" js"', root)

    def test_portal_catalog_has_only_populated_panels_no_js(self):
        """Catalog tabs expose every populated category and omit empty ones."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [
                    ("lessons/0001.html", "第 1 课 · A"),
                    ("reference/r.html", "速查"),
                ]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            # Lessons and reference exist; review remains absent.
            self.assertIn('id="panel-lessons"', idx)
            self.assertIn('id="panel-reference"', idx)
            self.assertNotIn('id="panel-review"', idx)
            for h in ("lessons", "reference"):
                self.assertIn(f'href="#{h}"', idx)
            # No JS class baked into static HTML.
            self.assertNotIn('class="js"', idx)

    def test_portal_existing_tab_structure_unchanged(self):
        """Existing hash/tab generation structure must still work after CSS change."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability", [
                    ("lessons/0001.html", "第 1 课 · A"),
                    ("lessons/0002.html", "第 2 课 · B"),
                    ("reference/r.html", "速查"),
                ]),
            ])
            out = Path(temp) / "portal"
            result = subprocess.run(
                [sys.executable, str(scripts / "build_portal.py"),
                 "--workspace", str(ws), "--out", str(out),
                 "--project", "pmp-certification"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            idx = (out / "pmp" / "index.html").read_text(encoding="utf-8")
            # aria-selected and data-active attributes still generated.
            self.assertIn('aria-selected="true"', idx)
            self.assertIn('data-active="true"', idx)
            self.assertIn('data-active="false"', idx)
            # tablist role and data-group still present.
            self.assertIn('role="tablist"', idx)
            self.assertIn('data-group="catalog"', idx)
            # Tab IDs and hash routing intact.
            self.assertIn('id="tab-lessons"', idx)
            self.assertIn('data-hash="lessons"', idx)

    _EXPORT_LESSON_HTML = (
        '<!doctype html><html lang="en"><head>'
        '<link rel="stylesheet" href="../assets/lesson.css">'
        '<title>第 1 课 · A</title></head>'
        '<body data-ui-version="2" data-pipeline="capability" '
        'data-format="reference" data-theme="overview">'
        '<main class="lesson-shell" id="main"><header class="lesson-header">'
        '<h1>第 1 课 · A</h1></header><section class="reference-section">'
        '<h2>Content</h2></section><footer class="lesson-footer">'
        '<p>Done</p></footer></main>{payload}'
        '<script src="../assets/lesson.js"></script></body></html>'
    )

    def _run_offline_export(self, temp, payload="", html=None, css=None):
        """Build a one-lesson fixture, run the offline exporter, return (result, out)."""
        scripts = Path(__file__).resolve().parent
        self._portal_multi(temp, [
            ("test-project", "Test", "capability",
             [("lessons/0001.html", "第 1 课 · A")]),
        ])
        proj = Path(temp) / "workspace" / "projects" / "test-project"
        if css is not None:
            (proj / "outputs" / "assets" / "lesson.css").write_text(css, encoding="utf-8")
        lesson = proj / "outputs" / "lessons" / "0001.html"
        lesson.write_text(
            html if html is not None else self._EXPORT_LESSON_HTML.format(payload=payload),
            encoding="utf-8")
        out = Path(temp) / "0001.offline.html"
        result = subprocess.run(
            [sys.executable, str(scripts / "export_offline_lesson.py"),
             "--file", str(lesson), "--out", str(out)],
            capture_output=True, text=True)
        return result, out

    def _assert_offline_rejected(self, result, out):
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertFalse(out.exists(), "output must not exist on rejection")

    def test_offline_export_unquoted_stylesheet_attr(self):
        """Unquoted stylesheet attributes must inline cleanly, no residual dependency."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                '<link rel="stylesheet" href="../assets/lesson.css">',
                "<link rel=stylesheet href=../assets/lesson.css>")
            result, out = self._run_offline_export(temp, html=html)
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = out.read_text(encoding="utf-8")
            self.assertIn("<style>", exported)
            self.assertNotIn("../assets/lesson.css", exported)
            self.assertNotIn('<link rel="stylesheet"', exported.lower())

    def test_offline_export_self_closing_stylesheet(self):
        """Self-closing <link ... /> must inline without leaving a dangling tag."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                '<link rel="stylesheet" href="../assets/lesson.css">',
                '<link rel="stylesheet" href="../assets/lesson.css" />')
            result, out = self._run_offline_export(temp, html=html)
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = out.read_text(encoding="utf-8")
            self.assertIn("<style>", exported)
            self.assertNotIn("lesson.css", exported)

    def test_offline_export_rejects_file_uri_css(self):
        """file:// stylesheet must be rejected, no output."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                'href="../assets/lesson.css"', 'href="file:///etc/passwd"')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_non_stylesheet_link(self):
        """Non-stylesheet <link href> (e.g. icon) must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                "</head>", '<link rel="icon" href="https://x/fav.ico"></head>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_srcset(self):
        """srcset attribute must be rejected (external resource channel)."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<img srcset="a.jpg 1x">')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_poster(self):
        """video poster attribute must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<video poster="x.jpg"></video>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_track_src(self):
        """track src attribute must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<track src="en.vtt">')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_base_href(self):
        """<base href> must be rejected (redirects relative URLs)."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                "</head>", '<base href="https://evil/"></head>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_meta_refresh(self):
        """meta refresh must be rejected (navigation/redirect channel)."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                "</head>", '<meta http-equiv="refresh" content="0;url=https://x"></head>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_link_preload(self):
        """<link rel=preload/imagesrcset> must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                "</head>", '<link rel="preload" href="https://x/f.js" as="script"></head>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_iframe_srcdoc(self):
        """iframe srcdoc must be rejected (embedded active document)."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<iframe srcdoc="<script>1</script>"></iframe>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_form_action(self):
        """form action attribute must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<form action="https://x"></form>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_anchor_ping(self):
        """anchor ping attribute must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<a href="https://ok.example" ping="https://track">x</a>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_onclick(self):
        """on* event handler attribute must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<button onclick="alert(1)">x</button>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_javascript_href(self):
        """javascript: href must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<a href="javascript:alert(1)">x</a>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_javascript_href_newline_encoded(self):
        """Newline-obfuscated javascript: href must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<a href="java\nscript:alert(1)">x</a>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_arbitrary_inline_script(self):
        """Executable inline script (no JSON type) must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="<script>alert(1)</script>")
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_duplicate_type_attr(self):
        """Duplicate attribute on a tag must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                "</body>", '<script id="lesson-questions" type="application/json" '
                'type="application/json">{"q":1}</script></body>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_css_escape(self):
        """CSS identifier escape (backslash escape) must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            result, out = self._run_offline_export(temp, css="body{background:u\\72l(x)}")
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_css_url(self):
        """CSS url() must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            result, out = self._run_offline_export(temp, css="body{background:url(x.png)}")
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_wrong_asset_name(self):
        """Only lesson.css/lesson.js may be inlined; another assets-root CSS is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            assets = proj / "outputs" / "assets"
            (assets / "other.css").write_text("body{color:red}", encoding="utf-8")
            lesson = proj / "outputs" / "lessons" / "0001.html"
            lesson.write_text(self._EXPORT_LESSON_HTML.format(payload="").replace(
                'href="../assets/lesson.css"', 'href="../assets/other.css"'), encoding="utf-8")
            out = Path(temp) / "0001.offline.html"
            result = subprocess.run(
                [sys.executable, str(scripts / "export_offline_lesson.py"),
                 "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_inline_style_attr(self):
        """style= attribute must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<div style="color:red">x</div>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_inline_svg(self):
        """Inline SVG must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="<svg><circle/></svg>")
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_rejects_data_iframe(self):
        """data: iframe src must be rejected."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload='<iframe src="data:text/html,<b>x</b>"></iframe>')
            result, out = self._run_offline_export(temp, html=html)
            self._assert_offline_rejected(result, out)

    def test_offline_export_denetworks_audio_config(self):
        """audio-config keeps lang, drops remote TTS, forces allow_remote_tts=false."""
        with tempfile.TemporaryDirectory() as temp:
            html = self._EXPORT_LESSON_HTML.format(payload="").replace(
                "</body>", '<script id="audio-config" type="application/json">'
                '{"lang":"zh","allow_remote_tts":true,"online_tts":"https://x/tts",'
                '"online_dictionary":"https://x/dict"}</script></body>')
            result, out = self._run_offline_export(temp, html=html)
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = out.read_text(encoding="utf-8")
            self.assertIn('id="audio-config"', exported)
            self.assertIn('"allow_remote_tts":false', exported)
            self.assertIn('"lang":"zh"', exported)
            self.assertNotIn("online_tts", exported)
            self.assertNotIn("online_dictionary", exported)

    def test_offline_export_failure_creates_no_output_dir(self):
        """Rejection must not create the output parent directory."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            lesson = proj / "outputs" / "lessons" / "0001.html"
            lesson.write_text(self._EXPORT_LESSON_HTML.format(
                payload='<img src="https://x/a.jpg">'), encoding="utf-8")
            out = Path(temp) / "deep" / "nested" / "x.offline.html"
            result = subprocess.run(
                [sys.executable, str(scripts / "export_offline_lesson.py"),
                 "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
            self.assertFalse((Path(temp) / "deep").exists(),
                             "rejection must not create the output parent dir")

    def test_offline_export_preserves_existing_target_on_midwrite_change(self):
        """If the source hash diverges mid-write, an existing target is left intact."""
        import importlib
        scripts = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts))
        try:
            import export_offline_lesson as exp
            importlib.reload(exp)
            with tempfile.TemporaryDirectory() as temp:
                self._portal_multi(temp, [
                    ("test-project", "Test", "capability",
                     [("lessons/0001.html", "第 1 课 · A")]),
                ])
                proj = Path(temp) / "workspace" / "projects" / "test-project"
                lesson = proj / "outputs" / "lessons" / "0001.html"
                out = Path(temp) / "target.offline.html"
                out.write_text("SENTINEL", encoding="utf-8")
                real_sha = exp.sha256_file
                state = {"n": 0}
                def drifting(path):
                    state["n"] += 1
                    if state["n"] >= 3:  # post-write source-hash check
                        return "0" * 64
                    return real_sha(path)
                exp.sha256_file = drifting
                try:
                    returned = exp.export_offline(lesson, out)
                finally:
                    exp.sha256_file = real_sha
                self.assertEqual(returned, "")
                self.assertTrue(out.is_file(), "pre-existing target must be preserved")
                self.assertEqual(out.read_text(encoding="utf-8"), "SENTINEL")
        finally:
            if str(scripts) in sys.path:
                sys.path.remove(str(scripts))

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


    def test_offline_export_stylesheet_attr_order(self):
        """Stylesheet with href before rel must still inline and remove the tag."""
        import tempfile
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
            html_reordered = orig_html.replace(
                '<link rel="stylesheet" href="../assets/lesson.css">',
                '<link href="../assets/lesson.css" rel="stylesheet">')
            lesson.write_text(html_reordered, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.is_file())
            exported = out.read_text(encoding="utf-8")
            self.assertNotIn('<link rel="stylesheet"', exported.lower())
            self.assertNotIn('href="../assets/lesson.css"', exported)
            self.assertIn("<style>", exported)

    def test_offline_export_escape_path_rejected(self):
        """../ escape outside assets root must be rejected and produce no output."""
        import tempfile
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
            html_escape = orig_html.replace(
                'href="../assets/lesson.css"',
                'href="../../outside.css"')
            lesson.write_text(html_escape, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_offline_export_absolute_path_rejected(self):
        """Absolute path in ref must be rejected."""
        import tempfile
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
            html_abs = orig_html.replace(
                'href="../assets/lesson.css"',
                'href="/etc/passwd"')
            lesson.write_text(html_abs, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_offline_export_rejects_external_img(self):
        """Page with external image reference must be rejected."""
        import tempfile
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
            orig = lesson.read_text(encoding="utf-8")
            html_img = orig.replace("</body>",
                '<img src="https://example.com/photo.jpg"></body>')
            lesson.write_text(html_img, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_offline_export_rejects_external_audio(self):
        """Page with external audio reference must be rejected."""
        import tempfile
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
            orig = lesson.read_text(encoding="utf-8")
            html_audio = orig.replace("</body>",
                '<audio src="file:///tmp/secret.mp3"></audio></body>')
            lesson.write_text(html_audio, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_offline_export_rejects_css_import(self):
        """CSS containing @import must be rejected."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        export_script = scripts / "export_offline_lesson.py"
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            assets_dir = proj / "outputs" / "assets"
            css = assets_dir / "lesson.css"
            css.write_text('@import url("http://evil.com/bad.css");', encoding="utf-8")
            lesson = proj / "outputs" / "lessons" / "0001.html"
            out = Path(temp) / "0001.offline.html"
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_offline_export_json_scripts_preserved(self):
        """Inline JSON blocks survive export untouched."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        export_script = scripts / "export_offline_lesson.py"
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            lesson = proj / "outputs" / "lessons" / "0001.html"
            orig = lesson.read_text(encoding="utf-8")
            html_json = orig.replace("</body>",
                '<script id="lesson-questions" type="application/json">{"q":1}</script></body>')
            lesson.write_text(html_json, encoding="utf-8")
            out = Path(temp) / "0001.offline.html"
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = out.read_text(encoding="utf-8")
            self.assertIn('id="lesson-questions"', exported)

    def test_offline_export_rejects_symlink_asset(self):
        """Symlink assets must be rejected."""
        import tempfile, os
        scripts = Path(__file__).resolve().parent
        export_script = scripts / "export_offline_lesson.py"
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            assets_dir = proj / "outputs" / "assets"
            real_css = assets_dir / "lesson.css"
            real_css.unlink()
            (assets_dir / "real.css").write_text("body{color:red}", encoding="utf-8")
            os.symlink(str(assets_dir / "real.css"), str(assets_dir / "lesson.css"))
            lesson = proj / "outputs" / "lessons" / "0001.html"
            out = Path(temp) / "0001.offline.html"
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_offline_export_rejects_relative_img(self):
        """Relative image path must be rejected (not inlineable)."""
        import tempfile
        scripts = Path(__file__).resolve().parent
        export_script = scripts / "export_offline_lesson.py"
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("test-project", "Test", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            proj = Path(temp) / "workspace" / "projects" / "test-project"
            lesson = proj / "outputs" / "lessons" / "0001.html"
            orig = lesson.read_text(encoding="utf-8")
            html_img = orig.replace("</body>",
                '<img src="../assets/diagram.png"></body>')
            lesson.write_text(html_img, encoding="utf-8")
            out = Path(temp) / "0001.offline.html"
            result = subprocess.run(
                [sys.executable, str(export_script), "--file", str(lesson), "--out", str(out)],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
    # ---- publish_portal wrapper tests ----

    def _portal_toml(self, temp, projects, publish=True, workspace=None):
        """Write a temporary portal.toml for test use."""
        if workspace is None:
            workspace = Path(temp) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        marker = workspace / "portal-markers.txt"
        marker.write_text("SECRET-MARKER\nPROJECT-PLAN\n", encoding="utf-8")
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
                ("pmp-certification", "Exam Prep", "capability",
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
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            (ws / "portal-markers.txt").write_text("SECRET-MARKER\n", encoding="utf-8")
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

    def test_publish_portal_rejects_disabled_incremental_publish(self):
        """A portal configured for preview-only cannot publish."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("pmp-certification", "Exam Prep", "capability",
                 [("lessons/0001.html", "第 1 课 · A")]),
            ])
            config = self._portal_toml(temp, ["pmp-certification"], publish=False)
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(config), "--publish"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("publish_after_validation is false", result.stderr)

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




    def test_publish_portal_rejects_missing_marker_file(self):
        """Missing marker_file in config is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "portal.toml"
            p.write_text(
                "[portal]\n"
                'projects = ["tp"]\n',
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(Path(temp) / "ws"),
                 "--config", str(p),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("marker_file", result.stderr.lower())

    def test_publish_portal_rejects_empty_marker_file(self):
        """Empty marker_file value is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "portal.toml"
            p.write_text(
                "[portal]\n"
                'marker_file = ""\n'
                'projects = ["tp"]\n',
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(Path(temp) / "ws"),
                 "--config", str(p),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("marker_file", result.stderr.lower())

    def test_publish_portal_rejects_missing_marker_on_disk(self):
        """Marker file configured but not present on disk is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = Path(temp) / "ws"
            ws.mkdir()
            p = Path(temp) / "portal.toml"
            p.write_text(
                "[portal]\n"
                'marker_file = "missing.txt"\n'
                'projects = ["tp"]\n',
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(p),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr.lower())

    def test_publish_portal_rejects_directory_as_marker(self):
        """A valid project still rejects a directory marker at the marker gate."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [("tp", "TP", "capability", [])])
            (ws / "markers").mkdir()
            p = Path(temp) / "portal.toml"
            p.write_text(
                "[portal]\n"
                'marker_file = "markers"\n'
                'projects = ["tp"]\n',
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(p),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a regular file", result.stderr.lower())

    def test_publish_portal_rejects_escape_marker_path(self):
        """A valid project still rejects an escaping marker path at the marker gate."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [("tp", "TP", "capability", [])])
            p = Path(temp) / "portal.toml"
            p.write_text(
                "[portal]\n"
                'marker_file = "../outside.txt"\n'
                'projects = ["tp"]\n',
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws),
                 "--config", str(p),
                 "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("simple relative path", result.stderr.lower())

    def test_publish_portal_build_uses_immutable_marker_snapshot(self):
        """A source rewrite after validation cannot change the markers sent to build."""
        scripts = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts))
        try:
            import publish_portal
            with tempfile.TemporaryDirectory() as temp:
                ws = self._portal_multi(temp, [
                    ("tp", "TP", "capability",
                     [("lessons/0001.html", "第 1 课 · A")]),
                ])
                marker_path = ws / "portal-markers.txt"
                marker_path.write_text("ZZ-MARKER\n# comment\n", encoding="utf-8")
                p = Path(temp) / "portal.toml"
                p.write_text(
                    "[portal]\n"
                    'marker_file = "portal-markers.txt"\n'
                    'repo = "../system"\n'
                    'projects = ["tp"]\n',
                    encoding="utf-8")
                captured = {}
                original_run = publish_portal._run
                def spy(cmd, label):
                    if any("build_portal.py" in str(c) for c in cmd):
                        captured["argv"] = [str(c) for c in cmd]
                        marker_path.write_text("REPLACED-MARKER\n", encoding="utf-8")
                        snapshot = Path(captured["argv"][captured["argv"].index("--markers") + 1])
                        captured["snapshot"] = snapshot
                        captured["contents"] = snapshot.read_text(encoding="utf-8")
                    return original_run(cmd, label)
                publish_portal._run = spy
                old_argv = sys.argv
                sys.argv = ["publish_portal.py", "--workspace", str(ws),
                            "--config", str(p), "--build-only"]
                try:
                    rc = publish_portal.main()
                finally:
                    sys.argv = old_argv
                    publish_portal._run = original_run
                self.assertEqual(rc, 0)
                self.assertIn("argv", captured, "build_portal.py was never invoked")
                argv = captured["argv"]
                self.assertIn("--markers", argv)
                self.assertNotEqual(argv[argv.index("--markers") + 1], str(marker_path.resolve()))
                self.assertEqual(captured["contents"], "ZZ-MARKER\n")
                self.assertFalse(captured["snapshot"].exists(), "snapshot must be cleaned up")
        finally:
            if str(scripts) in sys.path:
                sys.path.remove(str(scripts))

    def test_publish_portal_rejects_marker_replaced_by_symlink_before_read(self):
        """The source marker is read through O_NOFOLLOW after the path checks."""
        import os, unittest.mock as mock
        scripts = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts))
        try:
            import publish_portal
            with tempfile.TemporaryDirectory() as temp:
                ws = Path(temp) / "ws"; ws.mkdir()
                marker = ws / "marker.txt"
                marker.write_text("SAFE\n", encoding="utf-8")
                external = Path(temp) / "external.txt"
                external.write_text("EXTERNAL\n", encoding="utf-8")
                original_read = publish_portal._read_regular_file
                replaced = False
                def replace_then_read(path):
                    nonlocal replaced
                    if not replaced:
                        marker.unlink()
                        os.symlink(external, marker)
                        replaced = True
                    return original_read(path)
                with mock.patch.object(publish_portal, "_read_regular_file", replace_then_read):
                    with self.assertRaises(SystemExit):
                        publish_portal._validate_marker_file(ws.resolve(), "marker.txt")
                self.assertTrue(replaced)
        finally:
            sys.path.remove(str(scripts))

    def test_publish_portal_rejects_snapshot_replaced_before_deploy(self):
        """A snapshot replacement after build blocks deployment and is cleaned up."""
        scripts = Path(__file__).resolve().parent
        sys.path.insert(0, str(scripts))
        try:
            import publish_portal
            with tempfile.TemporaryDirectory() as temp:
                ws = self._portal_multi(temp, [("tp", "TP", "capability",
                                                [("lessons/0001.html", "第 1 课 · A")])])
                (ws / "portal-markers.txt").write_text("MARKER\n", encoding="utf-8")
                repo = Path(temp) / "repo"; repo.mkdir()
                for command in (("init",), ("checkout", "-b", "main"),
                                ("config", "user.email", "test@test"),
                                ("config", "user.name", "test")):
                    subprocess.run(["git", "-C", str(repo), *command], check=True,
                                   capture_output=True, text=True)
                (repo / "README.md").write_text("# test\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
                subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True,
                               capture_output=True, text=True)
                config = Path(temp) / "portal.toml"
                config.write_text('[portal]\npublish_after_validation = true\nrepo = "../repo"\nmarker_file = "portal-markers.txt"\n'
                                  'projects = ["tp"]\n', encoding="utf-8")
                original_run, labels, snapshot = publish_portal._run, [], []
                def replace_after_build(cmd, label):
                    labels.append(label)
                    result = original_run(cmd, label)
                    if label == "portal build":
                        path = Path(cmd[cmd.index("--markers") + 1])
                        replacement = path.with_name("replacement.txt")
                        replacement.write_text("REPLACED\n", encoding="utf-8")
                        replacement.replace(path)
                        snapshot.append(path)
                    return result
                publish_portal._run = replace_after_build
                old_argv = sys.argv
                sys.argv = ["publish_portal.py", "--workspace", str(ws),
                            "--config", str(config), "--publish"]
                try:
                    self.assertEqual(publish_portal.main(), 1)
                finally:
                    sys.argv = old_argv
                    publish_portal._run = original_run
                self.assertNotIn("portal deploy", labels)
                self.assertTrue(snapshot)
                self.assertFalse(snapshot[0].exists(), "snapshot must be cleaned up")
        finally:
            sys.path.remove(str(scripts))

    def test_publish_portal_rejects_absolute_marker_path(self):
        """Absolute marker_file path is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = Path(temp) / "ws"; ws.mkdir()
            p = Path(temp) / "portal.toml"
            p.write_text('[portal]\nmarker_file = "/etc/passwd"\nprojects = ["tp"]\n',
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(p), "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("marker_file", r.stderr.lower())

    def test_publish_portal_rejects_symlink_marker(self):
        """A marker file that is itself a symlink is rejected."""
        import os
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = Path(temp) / "ws"; ws.mkdir()
            (ws / "real.txt").write_text("MARKER-A\n", encoding="utf-8")
            os.symlink(str(ws / "real.txt"), str(ws / "marker.txt"))
            p = Path(temp) / "portal.toml"
            p.write_text('[portal]\nmarker_file = "marker.txt"\nprojects = ["tp"]\n',
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(p), "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("symlink", r.stderr.lower())

    def test_publish_portal_rejects_parent_symlink_marker(self):
        """A marker under a symlinked directory is rejected."""
        import os
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = Path(temp) / "ws"; ws.mkdir()
            realdir = ws / "realdir"; realdir.mkdir()
            (realdir / "marker.txt").write_text("MARKER-B\n", encoding="utf-8")
            os.symlink(str(realdir), str(ws / "linked"))
            p = Path(temp) / "portal.toml"
            p.write_text('[portal]\nmarker_file = "linked/marker.txt"\nprojects = ["tp"]\n',
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(p), "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("symlink", r.stderr.lower())

    def test_publish_portal_rejects_empty_marker_content(self):
        """A marker file with only whitespace/comments is treated as empty."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = Path(temp) / "ws"; ws.mkdir()
            (ws / "marker.txt").write_text("  \n# top comment\n  # indented comment\n",
                                           encoding="utf-8")
            p = Path(temp) / "portal.toml"
            p.write_text('[portal]\nmarker_file = "marker.txt"\nprojects = ["tp"]\n',
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(p), "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("no non-comment", r.stderr.lower())

    def test_publish_portal_rejects_non_utf8_marker(self):
        """A non-UTF-8 marker file is rejected."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = Path(temp) / "ws"; ws.mkdir()
            (ws / "marker.txt").write_bytes(bytes([0xFF, 0xFE]) + b"MARKER\n")
            p = Path(temp) / "portal.toml"
            p.write_text('[portal]\nmarker_file = "marker.txt"\nprojects = ["tp"]\n',
                         encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(p), "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("utf-8", r.stderr.lower())

    def test_publish_portal_rejects_marker_in_published_content(self):
        """Wrapper rejects when a published page contains a configured marker."""
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            ws = self._portal_multi(temp, [
                ("tp", "TP", "capability", [("lessons/0001.html", "第 1 课 · A")]),
            ])
            lesson = ws / "projects" / "tp" / "outputs" / "lessons" / "0001.html"
            lesson.write_text(lesson.read_text(encoding="utf-8").replace(
                "<p>Done</p>", "<p>SECRETZZ</p>"), encoding="utf-8")
            (ws / "portal-markers.txt").write_text("SECRETZZ\n", encoding="utf-8")
            p = Path(temp) / "portal.toml"
            p.write_text(
                "[portal]\n"
                'marker_file = "portal-markers.txt"\n'
                'repo = "../system"\n'
                'projects = ["tp"]\n',
                encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(scripts / "publish_portal.py"),
                 "--workspace", str(ws), "--config", str(p), "--build-only"],
                capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("marker", r.stderr.lower())
if __name__ == "__main__":
    unittest.main()
