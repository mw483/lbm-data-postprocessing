# 2026-10-05: CLAUDE.md rule "Ask, don't assume"

Commit: `ddaee2a`.

## Context

On 2026-10-05 the owner (Mikael) asked that CLAUDE.md say: if anything about the repository or the purpose of the research is unclear, ask instead of assuming. He also said the research focuses on facts in the data and statistics on them, not on assumptions.

## Decisions

- The rule goes at the top of CLAUDE.md, above the workflow steps, so it applies to every step.
- The workflow steps were not changed.
- No code changed.

## Changes

| File | What changed | Why |
|---|---|---|
| `CLAUDE.md` | Added a paragraph "**Ask, don't assume.**" before "Follow this workflow...". It says to ask Mikael when the repository or the research purpose is unclear, and that the research works from facts in the data and statistics on them. | Owner's request above. |

## How it was checked

Read the diff: one file, two lines added (the paragraph and a blank line). Nothing was run or tested, because no code changed.

## Open items and known limits

None. The rule is a written instruction; nothing enforces it beyond the agent reading CLAUDE.md.

## How to see the change

```sh
git log --oneline HEAD~1..HEAD
git show ddaee2a
git diff HEAD~1 HEAD -- CLAUDE.md
```
