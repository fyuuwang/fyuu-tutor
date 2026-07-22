# Adaptive teaching loop

Use this loop across every pipeline. Project-specific rules may make evidence stricter but may not collapse or skip levels.

## Evidence levels

- **Produced**: the lesson or aid exists and passed relevant deterministic checks.
- **Studied**: the learner explicitly confirms using the artifact or leaves equivalent activity evidence.
- **Demonstrated**: the learner independently explains, answers, produces, or applies the target with recorded evidence.
- **Stable**: the learner demonstrates it again after a delay or in a changed context under the project's threshold.

Never infer Studied from file existence, Demonstrated from Studied, or Stable from one successful attempt.

## Choose the next teaching step

Find the earliest concept, symbol, method, prerequisite, or production step that blocks progress. Teach that one hinge instead of explaining all possible background. Trust a learner's statement that earlier material is known provisionally, then revise only when evidence contradicts it.

Use short teach-and-check cycles. When the learner should supply the next step, ask and stop.

## Choose the visual theme

When producing a lesson or reference page for the first time, confirm the page theme with the learner. Themes express knowledge domain, not aesthetic preference:

- `overview`: cross-domain integration, maps
- `people`: team, communication, stakeholders
- `process`: delivery, methods, controls
- `business`: value, governance, business environment
- `review`: review, mistakes, mock exams

A `reference` page may use section-level themes to let color carry information hierarchy. Suggest a theme mapping when the learner is unsure; record the choice so other agents stay consistent.

## Route errors to interventions

Record the task, learner response, expected model, evidence, and likely error type. Match the repair:

| Error | Efficient intervention |
|---|---|
| Notation or object-role confusion | Translate symbols or objects into ordinary language |
| Wrong concept model | Build an intuition bridge, contrast, or concrete example |
| Wrong method selection | Compare problem cues and method boundaries |
| Setup or representation failure | Translate words into variables, structure, dialogue, diagram, or state |
| Reasoning or proof gap | Identify the missing hinge, invariant, assumption, or decision rule |
| Local calculation or pronunciation slip | Correct locally and add a checking habit |
| Transfer failure | Name the reusable pattern and give a near-transfer task |
| Overgeneralization | Use a counterexample or edge case |
| Memorized procedure without mechanism | Ask a why-step or explain-it-back check |

Do not answer every error with a full re-explanation. Keep unresolved errors active and reuse them in later retrieval, production, or transfer tasks. Record every new attempt separately.

## Decide readiness

Use current-concept evidence, not a general impression:

- **Advance**: independent reasoning and application are sound; required transfer evidence is present.
- **Advance with caution**: core use is sound but consistency or transfer remains thin; check early in the next lesson.
- **Review first**: one local gap should be repaired before continuing.
- **Step down**: a prerequisite, notation, object type, or cognitive-load problem blocks the current level.
- **Diagnose again**: the goal or evidence is missing, ambiguous, or contradictory.
- **More practice needed**: supported performance works, but independent use is not stable.

One correct answer or one fluent repetition is insufficient. Prefer independent explanation, production, near-transfer, changed-context use, and delayed retrieval over recognition.

Readiness decisions choose the next action; they do not create a second mastery ledger.

## Validate artifacts

Before marking an artifact Produced:

1. Run `validate_project.py`.
2. Run the selected pipeline's smallest content check.
3. Run `check_links.py`.
4. Rebuild indexes after changing HTML output or `STATUS.md`.
5. Record manual uncertainty explicitly.
