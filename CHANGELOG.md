# Changelog

All notable changes are recorded here. Preview releases may contain breaking changes, which must include migration notes.

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
