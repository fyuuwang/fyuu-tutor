---
name: fyuu-tutor
description: Operate long-running, document-backed tutoring projects that turn trusted materials or goals into adaptive HTML lessons, practice, and evidence-guided next steps. Use when creating, continuing, reviewing, or handing off a private learning project; auditing source materials; planning a curriculum; generating lessons or reference aids; recording learner evidence; or routing a project through capability, certification, or language tutoring.
---

# Fyuu Tutor

Treat project files as the control plane. Keep reusable tutoring logic in this Skill and all learner data, sources, generated content, and live state in the private project.

## Route the project

Choose the primary pipeline by the evidence that will prove success:

- **Capability**: the learner must explain, apply, build, decide, or transfer. Read [capability.md](references/pipelines/capability.md).
- **Certification**: the learner must satisfy a dated exam outline and perform under exam conditions. Read [certification.md](references/pipelines/certification.md).
- **Language**: the learner must understand or produce a target language. Read [language.md](references/pipelines/language.md).

If the success evidence is ambiguous, ask one question that would change the route. Do not route by input format: a PDF, topic, case, or question bank can support any suitable pipeline.

## Start

1. Locate the project and require `project.toml` plus `pipeline.toml`.
2. Run `python3 scripts/validate_project.py --project <project-dir>`.
3. Read [core.md](references/core.md) and [project-schema.md](references/project-schema.md).
4. Read the selected pipeline above. When materials must be acquired or converted, also read [material-pipeline.md](references/material-pipeline.md).
5. Read [teaching-loop.md](references/teaching-loop.md) before planning a lesson, evaluating an attempt, or choosing the next step.
6. Before producing any lesson HTML, read [ui-contract.md](references/ui-contract.md) and confirm the UI kit is installed.
7. Read the declared private profile, then `MISSION.md`, `NOTES.md`, `CURRICULUM.md` when present, and `STATUS.md`.

## Operate

1. Confirm synchronization and require `STATUS.md` to be `idle`.
2. Claim one bounded project task with `update_status.py` before changing project artifacts.
3. Preserve source files and keep production, study, demonstrated performance, and stable mastery distinct.
4. Apply the shared material and teaching loops plus only the selected pipeline.
5. Put generated lessons, aids, evidence, and history only in the project paths declared by `project.toml`.
6. Run deterministic checks and record remaining manual uncertainty.

Pipeline defaults yield to the private learner profile and project rules for teaching choices. Nothing may override the safety and state rules in `core.md`.

## Finish

1. Run the project validator, the smallest pipeline-specific check, and `check_links.py`.
2. Record produced artifacts, learner evidence, unresolved errors, blockers, and one next action separately.
3. Rebuild indexes after changing HTML output or `STATUS.md`.
4. Release the claim and verify `STATUS.md` is `idle`.

## Deterministic tools

- Project lifecycle: `scripts/create_project.py`, `validate_project.py`, `update_status.py`.
- Output checks: `scripts/check_links.py`, `build_index.py`, `audit_privacy.py`.
- Material processing: `scripts/pdf/`.
- Optional pipeline implementations: `scripts/pipelines/`.
- UI kit: `scripts/sync_ui_kit.py` (install/check/upgrade) and `scripts/validate_lesson_ui.py` (--file/--project/--kit/--self-test).
- Learning portal: `scripts/build_portal.py` (explicit `--project` only; never publishes all projects by default). Deployment via `scripts/deploy_portal.sh` requires user authorization and `--publish`.
- Offline export: `scripts/export_offline_lesson.py` creates a self-contained single-file HTML by inlining local `lesson.css` and `lesson.js`. Use it when a reader needs a standalone copy for Safari or offline reading. It rejects remote resources, `file://` links, and missing assets and never modifies the source file.
- Portal publish wrapper: `scripts/publish_portal.py` reads a private `<workspace>/portal.toml` to determine which projects to publish, runs all validators, builds the portal, scans for private data, and calls `deploy_portal.sh --publish`. After a course is produced and the claim is released, run this wrapper with `--publish` if `<workspace>/portal.toml`'s `publish_after_validation` is true. If publishing fails, record the failure reason in STATUS.md without changing course status. Never bypass the wrapper to copy private directories into gh-pages.

Do not install dependencies, publish content, expose private sources, or resolve another agent's claim without explicit user authority.
