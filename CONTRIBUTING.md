# Contributing

Use a focused branch and open a pull request against `main`.

Before submitting:

```bash
python3 fyuu-tutor/scripts/test_fyuu_tutor.py
python3 fyuu-tutor/scripts/check_links.py --root .
python3 fyuu-tutor/scripts/audit_privacy.py --system .
```

Keep reusable rules in the Skill and real learner data in private projects. Never submit textbooks, source extracts, generated lessons, learner profiles, evidence records, absolute local paths, credentials, or copyrighted question banks.

Changes to pipeline identifiers, project schema, status fields, or script arguments require a changelog migration note. Keep `SKILL.md` under 500 lines and avoid new dependencies unless the standard library cannot meet a demonstrated need.
