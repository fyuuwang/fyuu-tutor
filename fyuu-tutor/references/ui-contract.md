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
| `reference` | Formula maps, cheatsheets, knowledge maps | Header -> Reference grid |

A mixed lesson uses the `lesson` format. Only the quiz area switches to practice visuals automatically.

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

A `reference` page may use section-level `data-theme` to let color carry information hierarchy.

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

Two types are supported:

- `single_choice`: 2-6 options, `answer` is a valid index.
- `flashcard`: has `stem`, `answer_text`, and optional `rationale`.

Rules:

- Every question must have a stable `id`. Reordering pages must not change IDs.
- Stem, options, and rationale are plain text. No HTML.
- The JS renders questions using DOM API and `textContent`.


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

The adapter tries `speechSynthesis`, then remote TTS (only if `allow_remote_tts` is true and HTTPS), then opens the fallback URL. Config must be pure JSON, HTTPS only, no keys or tokens. `single_choice` questions may carry an optional `audio_text` field for listening exercises.

## What you must not do

- No `<style>` tags or `style=""` attributes.
- No remote fonts, scripts, or resources.
- No inline JavaScript except the JSON question block.
- No new CSS classes. Use only approved components.
- No copying shared assets into per-lesson files.
- No modifying `outputs/assets/` or `outputs/templates/` directly.
- No remote TTS without explicit `allow_remote_tts: true` and HTTPS.
- No production task without a stable `data-item-id`.

## Adding a new component

A new component requires simultaneous updates to all five:

1. The component HTML in `outputs/templates/components.html`.
2. The CSS in the shared stylesheet.
3. The entry in `ui-spec.json` `components`.
4. The gallery preview.
5. A validator test case.

No single-lesson custom components. Ever.

## Safari note

Safari does not reliably render `file://` pages with `@import` CSS. Use a local HTTP server for preview:

```bash
cd outputs && python3 -m http.server 8000
```

Open `http://localhost:8000/lessons/your-page.html`.
