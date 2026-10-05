# Working agreement

**Ask, don't assume.** If anything about the repository or the purpose of the research is unclear, ask Mikael instead of assuming. The research works from facts in the data and statistics on them, not from assumptions.

Follow this workflow for every change to this repository:

1. **Discuss and plan first.** Understand the current state, let Mikael explain the goal, confirm the details, and present a plan for the change.
2. **Change nothing until Mikael approves the plan.** No edits, commits or pushes before an explicit approval in chat.
3. **Write the changelog after committing.** Once the approved change is committed, run the `changelog-writer` subagent (`.claude/agents/changelog-writer.md`, runs on Sonnet). Give it the commit range and a brief on the goal and the reasons behind each change. Review what it wrote, then commit the changelog files.

The changelog lives in `changelog/`. Its `README.md` indexes every entry.
