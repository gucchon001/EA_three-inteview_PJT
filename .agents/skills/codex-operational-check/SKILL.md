---
name: codex-operational-check
description: Run reusable Codex operations checks before, during, and after work so prompts, planning, verification, durable guidance, skills, MCP, automations, threads, and subagents are used at the right time. Triggers: Codex best practices, 運用チェック, ベストプラクティス運用, 進め方を点検, AGENTS/rules/skillsへ昇格, セッション運用.
---

# Codex Operational Check

Use this skill when starting, steering, finishing, or retrospecting Codex work. Keep it lightweight: the output should usually be a short checklist or a few corrective actions.

## Pre-Task Readiness Check

- Prompt shape: Confirm the task has a clear `Goal`, `Context`, `Constraints`, and `Done when`. If any are missing and the work is ambiguous, ask before implementing.
- Task scope: Keep one coherent task per thread. Split unrelated objectives into separate follow-ups or threads.
- Planning: For difficult, risky, broad, or unclear work, plan first. Separate investigation, plan, implementation, and verification.
- Durable guidance: Read applicable `AGENTS.md` guidance and treat it as the repo's durable operating contract.
- External context: Use MCP/connectors or browsing when the answer depends on changing external state, authenticated systems, current docs, or remote project data.
- Bounded delegation: Use subagents only for bounded exploration, tests, triage, or review with a clear read/write scope and return format.

## Mid-Task Operation Check

- Scope control: Confirm edits remain inside the requested ownership boundary. Do not revert or overwrite other people's changes.
- Course correction: If new facts change the approach, update the plan before continuing.
- Evidence trail: Keep notes on commands, test results, files changed, and decisions that should survive the thread.
- Repeatability: If the same procedure appears likely to recur, mark it as a candidate skill or script instead of relying on memory.
- Automation restraint: Do not create automations until the human workflow is stable, repeated, and well understood.

## Final Done Check

- Done criteria: Match the result against the user's `Done when` and any repo-specific acceptance criteria.
- Verification: Run the relevant tests, lint, typecheck, build, review, screenshots, or CLI checks. Tests and review are part of done.
- Unverified work: If a check cannot run, state exactly what was not verified and why.
- Handoff: Report changed files, checks run, and blockers/risks. Keep it short and factual.

## Retrospective Promotion Check

After completion, decide whether any lesson should be promoted:

- `AGENTS.md`: durable repo guidance that should be loaded every turn.
- Rules/hooks: rules that must be enforced consistently or automatically.
- Skills: repeatable workflows, checklists, or domain procedures.
- Automations: stable recurring workflows that no longer need ad hoc judgment.

Promote only when the guidance is reusable, current, and specific enough to help future work.
