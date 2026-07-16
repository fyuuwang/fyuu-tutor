# Fyuu Tutor

[中文说明](README.zh-CN.md) · Current release: **v0.1.0 Preview**

Turn trusted material into a course that an AI tutor can actually continue.

Fyuu Tutor is a document-backed, adaptive tutoring skill for Codex. Give it a topic, textbook, question bank, or learning goal, and it can build and operate one of three learning paths:

- **Capability** — understand, apply, build, decide, and transfer.
- **Certification** — map an exam outline to lessons, questions, and readiness.
- **Language** — learn through context, active production, correction, and review.

Unlike a one-shot lesson generator, Fyuu Tutor keeps curriculum coverage, learner evidence, weak points, and the next action in a durable private project.

## Three things it does differently

### 1. Material to curriculum

Diagnose PDFs and other inputs, choose the smallest reliable extraction method, verify the result independently, and map every required unit before lessons are generated.

### 2. Three learning paths

| Path | Use it when success means |
|---|---|
| Capability | Explaining, deciding, building, applying, or transferring a skill |
| Certification | Covering a dated exam outline and performing under exam conditions |
| Language | Understanding or producing a target language in real situations |

The input format does not choose the path. The evidence required for success does.

### 3. Adaptive tutoring loop

Fyuu Tutor separates **Produced**, **Studied**, **Demonstrated**, and **Stable**. It records errors, selects the earliest blocking gap, produces the smallest useful next lesson, and re-tests weak areas after delay or in a changed context.

## Install

Python 3.11 or newer is required for the bundled scripts.

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo fyuuwang/fyuu-tutor \
  --path fyuu-tutor
```

The PDF helpers can use MarkItDown, RapidOCR, PyMuPDF, or Poppler when available. They are optional and are never installed automatically.

## Try it

```text
Use $fyuu-tutor to turn these systems-design concepts into a capability learning project and adapt the next lesson from my attempts.

Use $fyuu-tutor to map this exam outline and question bank into a certification curriculum with traceable coverage.

Use $fyuu-tutor to create an English-speaking project from these dialogues and require active production before advancing.
```

Create an empty project from the command line when you need a deterministic starting point:

```bash
python3 fyuu-tutor/scripts/create_project.py \
  --root ./private-learning/projects \
  --project-id systems-design \
  --display-name "Systems Design" \
  --pipeline capability
```

Use `--content-language zh-CN` for a Chinese project. Project sources, learner profiles, generated lessons, evidence, and live state remain outside this repository.

## How it works

1. Register and verify trusted material or goals.
2. Build a source-anchored learning and coverage map.
3. Route the project through one learning path.
4. Generate HTML lessons, practice, and compact reference aids.
5. Record evidence and errors, then select the next action.

The public Skill contains reusable rules, templates, and deterministic checks only. It must never contain real learning materials or learner data.

## Origins and additions

Fyuu Tutor is derived from Matt Pocock's [`teach`](https://github.com/mattpocock/skills/tree/main/skills/productivity/teach) skill. It retains and adapts the persistent teaching workspace, mission-grounded HTML lessons, learning records, zone-of-proximal-development selection, retrieval practice, spacing, interleaving, and feedback-loop ideas under the upstream MIT license.

Fyuu Tutor adds:

- capability, certification, and language routing;
- material diagnosis, OCR verification, normalization, and coverage mapping;
- four explicit evidence levels and error-to-intervention routing;
- dated certification authority and exam-outline controls;
- a versioned private-project schema and multi-agent claim protocol;
- privacy, link, project, and output validation scripts.

Bloom, Universal Diagnostic Tutor, AI Tutor Skill, Education Agent Skills, Mr. Ranedeer AI Tutor, and Tutor GPT informed product research only. No code or prompt text was copied from those projects. See [THIRD_PARTY_NOTICES.md](fyuu-tutor/THIRD_PARTY_NOTICES.md) for licenses and exact distinctions.

## Project status

`v0.1.0` is a public preview. Preview releases may contain breaking changes, but every such change must include a migration note. Strict semantic-versioning compatibility begins at `v1.0.0`.

See [CHANGELOG.md](CHANGELOG.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
