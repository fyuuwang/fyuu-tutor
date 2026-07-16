# Material-to-course pipeline

Use this shared pipeline whenever a tutoring project starts from external material or needs new factual grounding. Keep the original file read-only and keep every converted artifact inside the private project.

## 1. Register

Record the source owner, URL or local origin, access rights, authority level, version or effective date, verification date, local path, and intended use. For dated certifications, also record the next authority review date.

Do not convert material that is irrelevant, duplicated, unauthorized, or outside the project mission merely because it is available.

## 2. Diagnose the input

Identify the actual structure before choosing a tool:

- Text PDF: usable embedded text.
- Scanned PDF or image: no reliable text layer.
- Complex layout: tables, diagrams, slides, or multiple columns carry meaning spatially.
- Office file: rows, sheets, headings, or document structure are available natively.
- Topic only: no source exists yet, so acquire high-trust sources before teaching factual claims.

## 3. Extract with the smallest reliable method

- Text PDF: use MarkItDown as the normal reading source.
- Scan or image: render pages and use RapidOCR.
- Complex layout: keep the original file as spatial authority and add layout-preserving or visual checks.
- Office file: prefer its native structured reader over OCR or flattened text.

Do not run full OCR on a clean text PDF merely to create a second noisy copy.

## 4. Verify independently

Choose checks proportional to layout risk:

- file hash, page count, encryption and file type;
- character-count comparison against an independent extractor;
- representative phrase or per-page fragment sampling;
- expected item counts for questions, rows, sections, or sheets;
- visual inspection of weak pages, tables, diagrams, headings, and boundaries.

Record weak pages and manual limitations. A clean Markdown file does not prove that table geometry or diagrams survived.

## 5. Normalize without replacing the original

Create structured Markdown with stable headings and source anchors. Preserve the original file alongside it. Separate transcription from interpretation so later agents can distinguish source facts from course design.

## 6. Build the learning map

Extract the units required by the selected pipeline:

- concepts, capabilities, prerequisites, cases, exercises, questions, or language targets;
- source anchors for each unit;
- required coverage and explicit exclusions;
- missing authority, missing answers, ambiguous extraction, and other blockers.

## 7. Plan coverage before lessons

Map every required unit to a lesson, practice item, reference aid, or explicit exclusion. Design evidence of success before choosing teaching activities. Difficult or interesting topics alone never define a curriculum.

## 8. Produce and validate

Generate the smallest next artifact that follows the project curriculum and teaching loop. Validate source coverage, local links, output structure, pipeline-specific requirements, and remaining manual checks before marking it Produced.

Never copy source extracts, learner values, generated lessons, or project mappings into the Skill directory.
