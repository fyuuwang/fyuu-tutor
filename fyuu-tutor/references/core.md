# Core lifecycle and safety rules

## Non-overridable rules

- Source materials are read-only. Never overwrite, rename, or delete them during lesson production.
- `STATUS.md` is the only current state source.
- A produced artifact does not prove that the learner studied or mastered it.
- Do not modify a project already claimed by another agent or device.
- Do not install dependencies, publish packages, or expose private material without explicit authority.
- Stop when project rules conflict with these safety rules.

## Lifecycle

1. Validate project configuration.
2. Confirm synchronization and read current status.
3. Claim one bounded task with `update_status.py`; the claim lives only in `STATUS.md`.
4. Produce the smallest requested artifact.
5. Run automated checks and record any manual checks still required.
6. Update production progress, learner evidence, next action, and blockers separately.
7. Release the claim by returning status to `idle`.

`HANDOFF.md`, lock emoji lines, and legacy `_config/多Agent协作契约.md` files are historical context only. They never create, override, or release a claim.

## Completion

A task is complete only when the artifact exists, relevant checks pass, manual uncertainty is explicit, state is updated, and the claim is released.
