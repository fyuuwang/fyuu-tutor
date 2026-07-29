# Changelog

All notable changes are recorded here. Preview releases may contain breaking changes, which must include migration notes.

## [0.5.4] - Global Learning Navigation - 2026-07-29

### Changed

- Lesson, practice, and reference pages now keep their top navigation page-local and place learning-portal and course-route returns in one accessible bottom-right dock.
- Project course-route pages show only the learning-portal return; the learning portal root shows no self-referential return.
- Legacy UI v2 pages are normalized by the shared runtime without rewriting course content. Published copies receive explicit portal and course-route paths for runtime-created links.

### Fixed

- Global return links no longer consume space in lesson stage or reference section tabs.
- Mobile content reserves bottom safe-area space so the fixed dock cannot permanently obscure the final question, controls, or footer.

### Migration

- Run `sync_ui_kit.py --project <project> --upgrade` for installed projects, rebuild local indexes, then rebuild the public portal.

## [0.5.3] - Hardening Release - 2026-07-27

### Fixed

- Offline HTML exporter (`export_offline_lesson.py`) now opens source files via a file descriptor with `O_NOFOLLOW`, validates symlinks on the full path chain, and rejects unsupported external resources, `file://` links, `srcset`, `poster`, `track src`, `base href`, `meta refresh`, `link preload`, `iframe srcdoc`, `form action`, `anchor ping`, inline event handlers, `javascript:` URIs, inline scripts, duplicate type attributes, CSS escapes, CSS `url()`, wrong asset names, inline `style` attributes, inline SVGs, data iframes, and non-UTF-8 content rather than producing a partial output. It preserves `audio-config` only in an offline-safe form that disables remote TTS and online fallback. Attribute order, self-closing tags, and path-escape attempts no longer bypass validation.
- Portal publish wrapper (`publish_portal.py`) marker gate is now fail-closed: marker source files are read through `O_NOFOLLOW` file descriptors, a permission-restricted normalized snapshot is created for build and deploy, and the snapshot is verified by inode and content hash before every build and deploy step. Original marker files changed after validation can no longer affect the current run. Missing, empty, symlinked, parent-symlinked, non-UTF-8, and directory marker files are all rejected.
- Portal CSS no longer unconditionally hides `.panel` elements; panels are hidden only when `portal.js` adds a `js` class to `<html>`. Without JavaScript, all project entries and catalog links (课程 / 复习 / 资料) remain visible and reachable in source order.

### Changed

- README (EN and zh-CN) version references and Hero SVG version labels updated from `v0.3.0` / `v0.5.1` to `v0.5.3`. Offline export description no longer claims absolute self-containment; it states the exporter only accepts its recognized local shared resources and rejects unsupported external resources.

## [0.5.2] - Mobile Learning Portal - 2026-07-26

### Added

- Portal tab navigation: root page is a project switcher only (PMP / Cantonese / AI tabs, hash routing, default PMP); no lesson cards on the root page.
- Per-project catalog with secondary tabs (课程 / 复习 / 资料), stable sorting by leading number, and explicit empty states.
- Shared catalog-return component (`course-nav` / `course-back`) on lesson, reference, and practice pages; old UI v2 pages are backfilled at load time by `lesson.js`.
- Offline single-file HTML exporter (`export_offline_lesson.py`) that inlines `lesson.css` and `lesson.js`, rejects remote / `file://` dependencies, and never modifies the source file.
- Portal publish wrapper (`publish_portal.py`) that reads private `<workspace>/portal.toml`, runs all validators, builds the portal, scans for private data, and calls `deploy_portal.sh --publish`.

### Changed

- Web-first delivery: the HTTPS portal (`fyuuwang.github.io/fyuu-tutor`) is the recommended phone-based entry point; offline single-file HTML is for Safari, transfer, and archive use only.
- Mobile 01/02/03 stage bar now uses `grid-template-columns: repeat(3, 1fr)` (equal thirds, no horizontal scroll or overflow).
- `section-index` on reference pages restructured: `course-back` on the left, `section-index-links` row for chapter tabs.

### Fixed

- Mobile three-stage navigation offset and horizontal scroll eliminated.
- Portal root page no longer stacks lesson cards from all projects; is now a clean project switcher.
- Missing catalog-return button on short reference pages: `course-nav--simple` is now inserted at the top by `lesson.js`.

### Migration

- Run `sync_ui_kit.py --build-css` and `sync_ui_kit.py --project <project> --upgrade` for all three projects.
- Create a private `<workspace>/portal.toml` following the schema shown in `publish_portal.py --help`.

## [0.5.1] — Portal Deployment Patch — 2026-07-26

### Fixed

- The portal privacy scan now excludes a temporary deployment worktree's `.git` metadata while continuing to scan every published file.
- Added a regression test for the Git worktree deployment path.

## [0.5.0] — Safe Learning Portal and New Question Types — 2026-07-25

### Added

- Static learning portal (`build_portal.py`) with explicit `--project` selection; never publishes all projects by default.
- `true_false` and `matching` question types with validator, renderer, and self-test coverage.
- Shared `appendQuestionAudio` so single_choice, true_false, and matching all support `audio_text`.

### Changed

- Unified question runtime to a single field protocol; no more `_flash`/`opts`/`why` internal aliases.
- Matching scoring: 1 point only if completed without any wrong attempt; 0 if any wrong attempt occurred.
- Matching feedback: rationale visible only after completion; `hadError` tracked per question.
- Portal deployment (`deploy_portal.sh`) uses a temporary git worktree; never switches branches in the current worktree.

### Fixed

- Matching stale `selectedLeft` after correct lock; `Object.values(locked).indexOf()` for right-column disabled check.
- Boolean values no longer pass as single_choice integer answers.
- Matching rejects duplicate `right` items and unknown pair fields.
- Portal symlink detection, absolute-path scanning, and private-marker rejection.
- Output directory protection: refuses workspace root, project dirs, git root, and current directory.
- Privacy audit covers tracked + untracked-not-ignored files (git ls-files --cached --others --exclude-standard); rejects symlinks; scans ui-kit content but allows its HTML; adds /home/ and /private/ path rules.

- Source file protection: three scripts (ocr_pdf, convert_pronunciation, convert_pdf) now reject source==output and use tempfile+replace for safe writes.
- Portal: unique staging/backup names (tempfile.mkdtemp); rename-based atomic swap on same filesystem.
- Portal: validates UI Kit consistency before copying content.
- Deploy: all paths (--workspace, --repo, --markers) are now explicit required parameters.
- STATUS contract: \"Updated at\" added to required fields; owner/task/next-step protected against newlines and pipes.
- Validator: non-string question type IDs rejected instead of crashing; unknown script IDs rejected.
- Link rules: HTTPS <a> hrefs allowed with rel=noopener; remote resources only rejected for non-<a> elements.
- Matching: final feedback clears previous announce text before appending result.
- Matching: after a wrong pair, the next left-item click now clears the error and selects that item in one action.
- Audio controls now meet the 44 px minimum touch-target height.
- Portal builds now reject projects whose `STATUS.md` is not `idle`.
- Status claims reject blank or placeholder owners.
- Capability and language lessons now enforce non-empty, bounded learning maps; the Gallery lists every supported question type.
- CI: added py_compile, node --check, and bash -n stages.

### Security

- Portal defaults to publishing nothing; requires explicit `--project` per invocation.
- Only whitelisted files (lesson/reference HTML, CSS/JS assets) are copied; private index, Markdown, and other types are excluded.
- Deployment requires `--publish` flag; build-only mode is the default.

### Migration

- Run `sync_ui_kit.py --project <project> --upgrade` to update installed UI kit.
- Existing project content is not automatically published; portal requires explicit selection.
- Old `build_portal.py` calls without `--project` will fail; add explicit project IDs.

## [0.4.0] — One Frontend Pipeline — 2026-07-23

### Added

- Mandatory UI-kit installation for every new capability, certification, and language project.
- A 3 pipelines × 3 formats smoke matrix covering lesson, practice, and reference pages.
- Strict duplicate-attribute and closed section-index target/group validation.
- An explicit `sync_ui_kit.py --build-css` command for the checked-in single-file CSS bundle.

### Changed

- UI-kit install, check, and upgrade now share one payload and manifest path, including generated `lesson.css`.
- Reference tabs use the existing stage switcher and `aria-current`; the redundant intersection observer was removed.
- Reference composition guidance now separates shared rules from pipeline-specific advice.

### Fixed

- `sync_ui_kit.py --check` now detects a missing, modified, or stale project `lesson.css`.
- Installing or upgrading a project no longer modifies the installed Skill source.
- Section-index validation now rejects missing targets, duplicate targets, empty groups, orphan groups, invalid anchors, and one- or four-tab indexes.
- The PMP learning-map generator no longer emits duplicate `id` attributes.
- The UI validator now rejects pages that ship unfilled writing-guide placeholders (e.g. `[Scene title]`, `[Content]`), preventing a template skeleton from being published as finished content.

### Removed

- The obsolete Cantonese-only lesson validator; the shared UI validator now covers all three pipelines.

### Migration

- `create_project.py` no longer accepts `--ui-kit`; new projects always install the UI kit.
- Existing projects should run `sync_ui_kit.py --project <project> --upgrade`, then validate all output pages.
- Contributors changing split CSS files must run `sync_ui_kit.py --build-css` before the kit validator.

## [0.3.0] — Rich Learning Experiences — 2026-07-22

### Added

- A shipped UI Gallery, installed and integrity-checked with every UI kit.
- Canonical `UI-CONTRACT.md` installation for every UI-kit project.
- Strict component placement, production-task identity, JSON-question, and consented remote-TTS validation.

### Changed

- All three private projects now consume the same UI v2 kit: PMP, AI learning, and Cantonese learning.
- Quiz data is strict JSON only; legacy executable question objects are no longer accepted.
- Audio controls are named for assistive technology and use the full local speech → consented HTTPS TTS → visible fallback chain.

### Fixed

- Link checks ignore archived history, which is retained as evidence rather than a runnable site.
- Project creation no longer copies a second validator implementation.

### Migration

- Run `sync_ui_kit.py --project <project> --upgrade`, then validate every output page before release.

## [0.2.0] — Reusable UI Kit — 2026-07-22

### Added

- UI v2 kit: shared CSS, JS, templates, component catalog, gallery, and machine-readable `ui-spec.json`.
- Three formats (lesson, practice, reference) and five fixed themes (overview, people, process, business, review).
- `data-pipeline` body attribute routing pages to capability, certification, or language pipelines.
- New pipeline-specific components: dialogue, production-task, flashcard (language); worked-example, relation-net (capability).
- Strict JSON question format with stable IDs, `single_choice` and `flashcard` types, and HTML-injection rejection.
- `sync_ui_kit.py` for install, check, and upgrade of the shared UI kit in any project.
- `UI-CONTRACT.md` defining the page production interface for any agent.
- `validate_lesson_ui.py` v2: data-driven from `ui-spec.json`, with `--kit`, `--file`, `--project`, and `--self-test` modes.
- JavaScript i18n: localized feedback messages based on `<html lang>` (en and zh-CN).
- CI workflow now runs UI kit self-test and consistency checks.

### Changed

- Renamed PMP-specific component classes to generic names: `exam-map` to `learning-map`, `eco-table` to `coverage-table`.
- Questions switched from free-form JavaScript objects to strict JSON in `<script type="application/json">`.
- Step-number and scene-number now use Deep color for WCAG AA contrast across all themes.
- sessionStorage stage key now includes page path to prevent cross-lesson state leakage.
- Option labels extended from A-D to A-F.
- `create_project.py --ui-kit` now calls `sync_ui_kit.install()` instead of duplicating copy logic.

### Fixed

- Privacy audit now whitelists `assets/ui-kit/` HTML templates (production assets, not private content).
- `teaching-loop.md` visual theme section no longer interrupts the error-routing flow.
- Validator `load_spec` now finds `ui-spec.json` in both skill and project directory layouts.

### Migration (v1 to v2)

- PMP project fully migrated: all 19 learning pages now pass UI v2 validation.
- Question data verified identical: 501 questions, 81 reviewed, 26 tasks, 138 enablers unchanged.
- Old `pmp-lesson.css`, `pmp-lesson.js`, and `pmp-*` templates archived to `history/`.
- `sync_mapping.py` updated to parse JSON questions first, falling back to legacy patterns.

## [0.1.0] — Three Learning Paths — 2026-07-16

### Added

- Capability, certification, and language tutoring pipelines.
- Material diagnosis, extraction verification, normalization, and coverage mapping.
- Produced, Studied, Demonstrated, and Stable evidence levels.
- Error-to-intervention feedback loop and deterministic project tools.
- English-first schema v3 with localized English and Chinese indexes.

### Changed

- Generalized the original mission-grounded teaching workspace into a reusable, source-backed tutoring system.

### Fixed

- Separated reusable Skill logic from learner data, source material, generated lessons, and live project state.
