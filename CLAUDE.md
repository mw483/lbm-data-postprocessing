# Working agreement for this repository

How the owner (kaka) wants changes made. Follow these steps in order.

1. **Discuss first.** Read the current state, let the owner explain the goal, and ask about unclear details. Propose a plan and wait for confirmation. Do not edit anything yet.
2. **Change only after approval.** Make code, config, commit, push, merge and PR changes ONLY after the owner has approved the plan. Keep commits small and explain each in its message. Never commit to `main`.
3. **Write the changelog with the sub-agent.** After every change that is committed, run the `changelog-writer` sub-agent (`.claude/agents/changelog-writer.md`, Sonnet) on the new commits. Give it the commit range and the reasoning (the owner's request, decisions, what was checked and what was not). Read what it wrote, check it against the diff, fix mistakes, and commit it under `changelog/`.

The changelog goes in `changelog/`: one `YYYY-MM-DD_<topic>.md` per change, plus a row in `changelog/README.md`.
