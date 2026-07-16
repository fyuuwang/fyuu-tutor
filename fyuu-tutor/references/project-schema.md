# Private project interface

Every project contains:

```text
project.toml
pipeline.toml
MISSION.md
NOTES.md
STATUS.md
sources/
outputs/lessons/
outputs/reference/
records/
history/
```

Certification projects additionally require `CURRICULUM.md` and `sources/SOURCE-MAP.md`.

The generated browser entry is always `outputs/index.html`. Rebuild it after adding or renaming HTML output.

`project.toml` uses schema version 3 and declares `project_id`, `display_name`, `pipeline`, `content_language`, and relative paths. Valid pipeline identifiers are `capability`, `certification`, and `language`.

`pipeline.toml` uses schema version 3 and contains private values under the selected pipeline section. Never copy its real values into this Skill.

A certification section also declares its authority version, URL, verification date, next review date, authority source path relative to `sources/`, exam date, practice start, question and timing facts, and answer-source status. The validator rejects an overdue authority review; the operating agent still verifies current applicability against the authority.

Scripts resolve relative paths from the project directory. Absolute paths and paths escaping the private workspace are invalid, except the declared relative profile path.

`STATUS.md` must expose: State, Owner, Claimed at, Updated at, Production progress, Learning progress, Next action, Blockers.

Generated content belongs only under project paths. A Skill asset is an empty reusable template, never a completed lesson, learner record, or source extract.
