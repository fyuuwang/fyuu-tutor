# Security policy

Report vulnerabilities through GitHub's private security-advisory feature. Do not attach private learning materials, learner records, credentials, or copyrighted sources to a public issue.

The latest `v0.5.x` release is supported during the preview period. Fyuu Tutor reads and writes local project files, so path-boundary escapes, unintended source modification, private-data publication, and claim-protocol bypasses are security-relevant.
The learning portal (`build_portal.py`) publishes content to a public site, so the following are also security-relevant:
- Unauthorized course publication (portal requires explicit `--project` selection).
- Derived learning state leakage (private `outputs/index.html` and `STATUS.md` data must not enter the portal).
- Symlink path traversal (portal rejects symlinks in source directories).
