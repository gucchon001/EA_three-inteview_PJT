# Economics multi-student scope fixture

This fixture is synthetic. It preserves the shape of the static POC inputs
without copying real student, teacher, school, Google document, or household
identifiers.

Purpose:

- Exercise `prompt_scope_notes` for a multi-student meeting note.
- Keep the target and non-target blocks distinct.
- Support provider-mock tests without calling Google Workspace or OpenRouter.
