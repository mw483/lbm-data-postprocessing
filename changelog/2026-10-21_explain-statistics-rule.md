# CLAUDE.md rule for explaining statistics and figures (2026-10-21)

**Commits**: `47ddbb3` (range `ab6636e..47ddbb3`, one commit, `CLAUDE.md` only)

**Goal**: At the 2026-10-21 progress presentation Mikael focused on the results and could not clearly explain why statistics such as skewness and w'theta' were used. The next presentation is joint with a non-physics lab. So every figure or statistic now needs a plain-language explanation that a non-physicist can follow.

**Result**: Not tested. No code changed, and a written instruction cannot be run. The diff was read: one file, 9 lines added.

## Commit 47ddbb3: Add CLAUDE.md rule for explaining statistics and figures

| File | Change | Why |
|---|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | New section "Explaining statistics and figures" at the end of the file. It says every figure or statistic that is added, changed or presented must come with a short explanation (docstring, caption or chat), one line per point. | So Mikael can explain each statistic to a mixed audience, and the explanation is written down when the figure is made. |
| [`CLAUDE.md`](../CLAUDE.md) | Point 1, **What it measures**, in plain words a non-physicist can follow. | The next audience is a non-physics lab. |
| [`CLAUDE.md`](../CLAUDE.md) | Point 2, **Why this statistic**: first state the purpose of the analysis (for example validation against theory or a historical experiment, comparison between runs, a code check), then the physical question the statistic answers and why it was chosen over alternatives. | The missing piece on 2026-10-21 was the "why". Validation is the purpose of some analyses, not all, so the purpose is stated first and the statistic follows from it. |
| [`CLAUDE.md`](../CLAUDE.md) | Point 3, **Reference expectation**: the theory, experiment or published value it should match (examples: Willis & Deardorff tank, Stull 1988), with a citation. Anything not checked against the source is marked [U]. "If there is none, say so." | Results are only meaningful against an expectation. The last sentence lets analyses that are not validations (run comparison, code check) say there is no reference instead of inventing one. [U] is the mark already used in the project's literature notes for unchecked claims. |
| [`CLAUDE.md`](../CLAUDE.md) | Point 4, **Units, normalisation and sample**: for example /U_b, /w*, /z_i, and the averaging window and region. | So a number or profile is never shown without its scaling and the data it was averaged over. |

## How the wording was settled

Mikael reviewed a first draft. It ended with a closing line saying validation is the purpose of all analyses. He asked to drop it, because validation is the goal of only some analyses. The purpose is now asked for in point 2 instead. "If there is none, say so" was added to point 3 for the same reason: an analysis that is not a validation does not have to name a reference.

## What was deliberately left alone

- No code, scripts or existing figures were changed. The rule applies to figures and statistics added or presented from now on. Existing ones were not revisited.
- The three workflow steps and the "Ask, don't assume" rule in `CLAUDE.md` are unchanged. See [2026-10-05_ask-dont-assume.md](2026-10-05_ask-dont-assume.md).

## Context outside the repo

A separate self-test question set for this topic was written outside the repo (project files, `literature/study_questions_cbl_2026-10-21.md`). It is not part of this commit and is mentioned only as background.

## How to check

```sh
git show 47ddbb3
git diff ab6636e 47ddbb3 -- CLAUDE.md
```
