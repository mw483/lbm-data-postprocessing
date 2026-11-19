# Working agreement

**Ask, don't assume.** If anything about the repository or the purpose of the research is unclear, ask Mikael instead of assuming. The research works from facts in the data and statistics on them, not from assumptions.

Follow this workflow for every change to this repository:

1. **Discuss and plan first.** Understand the current state, let Mikael explain the goal, confirm the details, and present a plan for the change.
2. **Change nothing until Mikael approves the plan.** No edits, commits or pushes before an explicit approval in chat.
3. **Write the changelog after committing.** Once the approved change is committed, run the `changelog-writer` subagent (`.claude/agents/changelog-writer.md`, runs on Sonnet). Give it the commit range and a brief on the goal and the reasons behind each change. Review what it wrote, then commit the changelog files.

The changelog lives in `changelog/`. Its `README.md` indexes every entry.

## Explaining statistics and figures

Every figure or statistic you add, change or present must come with a short explanation (docstring, caption or chat), one line each:

1. **What it measures**, in plain words a non-physicist can follow.
2. **Why this statistic**: first state the purpose of the analysis (e.g. validation against theory or a historical experiment, comparison between runs, a code check), then the physical question the statistic answers and why it was chosen over alternatives.
3. **Reference expectation**: the theory, experiment or published value it should match (e.g. Willis & Deardorff tank, Stull 1988), with a citation. Mark anything not checked against the source as [U]. If there is none, say so.
4. **Units, normalisation and sample**: e.g. /U_b, /w*, /z_i, and the averaging window and region.
