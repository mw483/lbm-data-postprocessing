<<<<<<< HEAD
# Working agreement

Follow this workflow for every change to this repository:

1. **Discuss and plan first.** Understand the current state, let Mikael explain the goal, confirm the details, and present a plan for the change.
2. **Change nothing until Mikael approves the plan.** No edits, commits or pushes before an explicit approval in chat.
3. **Write the changelog after committing.** Once the approved change is committed, run the `changelog-writer` subagent (`.claude/agents/changelog-writer.md`, runs on Sonnet). Give it the commit range and a brief on the goal and the reasons behind each change. Review what it wrote, then commit the changelog files.

The changelog lives in `changelog/`. Its `README.md` indexes every entry.
=======
# Working agreement for this repository

How the owner (kaka) wants changes made. Follow these steps in order.

1. **Discuss first.** Read the current state, let the owner explain the goal, and ask about unclear details. Propose a plan and wait for confirmation. Do not edit anything yet.
2. **Change only after approval.** Make code, config, commit, push, merge and PR changes ONLY after the owner has approved the plan. Keep commits small and explain each in its message. Never commit to `main`.
3. **Write the changelog with the sub-agent.** After every change that is committed, run the `changelog-writer` sub-agent (`.claude/agents/changelog-writer.md`, Sonnet) on the new commits. Give it the commit range and the reasoning (the owner's request, decisions, what was checked and what was not). Read what it wrote, check it against the diff, fix mistakes, and commit it under `changelog/`.

The changelog goes in `changelog/`: one `YYYY-MM-DD_<topic>.md` per change, plus a row in `changelog/README.md`.
>>>>>>> dc78405e7376716e01be483ce26810767b5d0127
