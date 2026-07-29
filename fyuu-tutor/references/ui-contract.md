# UI Contract

This contract defines how learning pages look and behave. Every agent producing a lesson, practice, or reference page must follow it.

## Before you produce a page

1. Read this contract.
2. Run `sync_ui_kit.py --project <project> --check` to confirm the kit, including this contract, is installed and intact.
3. Choose a format (lesson, practice, or reference) from the templates.
4. Choose a theme. If the learner has not recorded a preference, ask once and record it.
5. Copy the corresponding template from `outputs/templates/`.
6. Fill in content using only approved components from `outputs/templates/components.html`.

## After you produce a page

1. Run the Skill's `validate_lesson_ui.py --file <page>` command.
2. Fix every error before committing.
3. Do not modify shared CSS, JS, or component internals.

## Formats

| Format | When | Structure |
|---|---|---|
| `lesson` | Teaching a concept through a case | Map -> Case -> Audit -> Practice |
| `practice` | Drills, flashcards, mock exams | Header -> Quiz |
| `reference` | Formula maps, cheatsheets, knowledge maps | Optional section index -> Header -> Chapter sections (chapter-header + reference-grid + takeaway) -> Footer |

A mixed lesson uses the `lesson` format. Only the quiz area switches to practice visuals automatically.

Short reference pages omit `section-index`. Pages with three or more chapters may group them into two or three balanced tabs. Each tab link uses a simple local target such as `#process`; that target must appear once as an element `id` and must match the `data-stage` of every chapter in the tab. Every tab needs at least one chapter, and no tab may contain more than three times another tab's reference items.

## Navigation return (course-home / course-back / course-nav)

Every lesson, reference, and practice page carries two shared return entries: `course-home` goes to the workspace learning portal; `course-back` goes to the current project's course route. New templates include them statically; old UI v2 pages are backfilled at load time by `lesson.js`.

In source HTML, `course-home` always points to `../../../index.html` and `course-back` to `../index.html`. The portal builder rewrites only its published copy to the flat public routes; course authors must not add GitHub Pages paths, localized project names, or custom public URLs.

On `lesson` pages the home icon, course-route return and 01/02/03 stage bar sit together in a `course-nav`. On mobile both return labels collapse to icons and the three stages split evenly with no horizontal scroll. Neither return entry is a stage or tab.

On `reference` pages `course-home` and `course-back` sit before the `section-index`; the link row holds the two or three chapter tabs. Short reference pages without a `section-index` get a `course-nav--simple` bar at the top instead. Return entries are not counted toward the three-tab limit.

On `practice` pages a `course-nav--simple` bar shows the two return entries; it does not fabricate a 01/02/03 stage bar.

Do not add per-page custom return link classes. `course-home` and `course-back` are the only sanctioned top return entries. The public portal may add bottom previous/next links to its copied pages; source lessons must not hard-code public routes.

## Themes

Themes express knowledge domain, not aesthetic preference. Fixed set only:

| Theme | Domain |
|---|---|
| `overview` | Cross-domain integration, maps |
| `people` | Team, communication, stakeholders |
| `process` | Delivery, methods, controls |
| `business` | Value, governance, business environment |
| `review` | Review, mistakes, mock exams |

Default recommendations by pipeline:

- `capability`: `overview` (alternatives: `process`, `business`)
- `certification`: `overview` (alternatives: `people`, `process`, `business`, `review`)
- `language`: `people` (alternatives: `overview`, `business`)

A `reference` page may use section-level `data-theme` to let color carry information hierarchy. In multi-section reference pages, each section's `data-theme` should reflect the content domain (e.g. `people` for team/communication, `process` for delivery/controls, `business` for value/governance), not default to `overview`.

## Body attributes

Every page declares:

```html
<body
  data-ui-version="2"
  data-pipeline="capability|certification|language"
  data-format="lesson|practice|reference"
  data-theme="overview|people|process|business|review">
```

Lesson pages also use `data-stage="map|case|practice"` on sections.

## Questions

Questions are declared as strict JSON in a `<script type="application/json">` tag:

```html
<script id="lesson-questions" type="application/json">
[
  {
    "id": "LESSON-0001-Q001",
    "type": "single_choice",
    "stem": "Question text",
    "options": ["A", "B", "C", "D"],
    "answer": 0,
    "rationale": "Why the answer is correct."
  }
]
</script>
```

Four types are supported:

- `single_choice`: 2-6 options, `answer` is a valid index.
- `flashcard`: has `stem`, `answer_text`, and optional `rationale`.
- `true_false`: `answer` is a boolean (`true`/`false`), no options array. Two large buttons rendered.
- `matching`: 3-6 `pairs` of `{left, right}`. Left and right texts must each be unique. Click left then right to pair. Scored as a whole: 1 point only if completed without any wrong attempt; 0 if any wrong attempt occurred during completion. Rationale shown only after completion.

Rules:

- Every question must have a stable `id`. Reordering pages must not change IDs.
- Stem, options, and rationale are plain text. No HTML.
- The JS renders questions using DOM API and `textContent`.

### Authoring input safely

- Generate a question block with a JSON serializer (for example, Python's `json.dumps(..., ensure_ascii=False)`); do not hand-assemble JSON escapes inside an HTML-writing command.
- Plain-text question fields must not contain literal `<` or `>` characters. State the comparison in words or use an appropriate Unicode comparison symbol such as `≤` or `≥`; HTML entities and escaped markup are not a formatting workaround because the renderer uses `textContent`.
- Component placement and pipeline eligibility are defined by `ui-spec.json`. In particular, use `quick-check` as an unscored scene/reference check, and use `production-task` only where the spec permits it.
- For a certification question, explain the tested principle or source and why the selected answer is the best action. A private certification project may impose stricter distractor-review rules.


## Production tasks and audio

A lesson practice stage may use scored questions, active production, or both. Use `data-component="production-task"` inside a `production-section` or `case-section`. Every production task needs a stable `data-item-id`:

```html
<details class="production-task" data-component="production-task" data-item-id="LESSON-XXXX-TASK-01">
  <summary>Say it first, then check</summary>
  <div class="production-task-body">
    <p class="production-prompt">How do you say this?</p>
    <textarea></textarea>
  </div>
</details>
```

Audio buttons use the shared adapter. Place an optional config block once per page:

```html
<button class="audio-trigger" type="button" data-text="你好" data-lang="zh-HK">🔊</button>
<script id="audio-config" type="application/json">
{"lang":"zh-HK","fallback_url":"https://words.hk/word/","allow_remote_tts":false}
</script>
```

The adapter tries `speechSynthesis`, then remote TTS (only if `allow_remote_tts` is true and HTTPS), then opens the fallback URL. Config must be pure JSON, HTTPS only, no keys or tokens. `single_choice`, `true_false`, and `matching` questions may carry an optional `audio_text` field for listening exercises; all three use the same audio adapter.


## Composition guidance

Different agents and models will produce pages for the same project. To keep information density and page rhythm consistent across agents, follow the `composition_patterns` in `ui-spec.json`. These are recommendations, not hard validation limits, but they define what "a normal lesson of this type looks like."

### Quality self-check (before committing)

Run through this list after the validator passes. Every item should be true.

**Structure**

- The map has the recommended number of nodes for this pipeline (see `composition_patterns`).
- Every map node links to a real scene with matching `id`.
- Each scene ends with a `takeaway` or `quick-check`, not just narrative.
- The audit section has a coverage-table (certification) or source list (capability/language).
- The practice stage has the recommended item count and type for this pipeline.
- If the page is reference format, chapter headers use `chapter-header`, not `scene`.
- Each chapter section ends with a takeaway.
- Section-level `data-theme` matches content domain (`people`/`process`/`business`), not all `overview`.

**Content**

- One case thread runs through all scenes. If the case changes mid-lesson, the narrative is broken.
- Every exam-related claim or judgment rule is traceable to a source in the audit section.
- Question rationales explain *why* the answer is correct, not just restate it.
- Production tasks require active output before revealing the model answer. Comprehension-only is not production.
- No placeholder text remains (`__LESSON_TITLE__`, `[Scene title]`, etc.).

**Consistency between agents**

- A second agent reading only this contract, `ui-spec.json`, and the template should be able to reproduce the same structure.
- If your page is meaningfully thinner or denser than its pipeline's composition pattern, adjust before committing.
- Theme choice reflects knowledge domain, not aesthetic preference. Do not swap themes just for color variety.

## What you must not do

- No `<style>` tags or `style=""` attributes.
- No remote fonts, scripts, or resources.
- No inline JavaScript except the JSON question block.
- No new CSS classes. Use only approved components.
- No copying shared assets into per-lesson files.
- No modifying `outputs/assets/` or `outputs/templates/` directly.
- No remote TTS without explicit `allow_remote_tts: true` and HTTPS.
- No production task without a stable `data-item-id`.
- No `scene` component in reference pages. Use `chapter-header` for section grouping.
- No section with 5+ reference-items and zero structured components when the content involves comparisons, definitions, or processes.

## Adding a new component

A new component requires simultaneous updates to all five:

1. The component HTML in `outputs/templates/components.html`.
2. The CSS in the shared stylesheet.
3. The entry in `ui-spec.json` `components`.
4. The gallery preview.
5. A validator test case.

No single-lesson custom components. Ever.

## Preview

`lesson.css` is a generated single-file bundle (no `@import`), so pages should render correctly when opened directly via `file://` in any browser. After changing `tokens.css`, `foundation.css`, or `components.css`, rebuild it with `python3 scripts/sync_ui_kit.py --build-css` and run the kit validator.

If you need a local HTTP server (e.g. for testing audio or fetch):

```bash
cd outputs && python3 -m http.server 8000
```

Open `http://localhost:8000/lessons/your-page.html`.
