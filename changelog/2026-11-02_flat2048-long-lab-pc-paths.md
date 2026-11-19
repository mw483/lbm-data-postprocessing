# flat2048_long reads the lab PC layout (2026-11-02)

**Commits**: `d6dd4d7` (branch `analysis/scalar2-outputs`)

**Goal**: The comment on the `flat2048_long` run said the rclone `Z:` drive was on the lab PC. Mikael said that was wrong: `Z:` is on his personal laptop. He moved the long-run data to the lab PC and works there now.

**Result**: `run_sets` loads and `tests/test_run_sets.py` passes. Not checked on the lab PC itself.

## Commit d6dd4d7: flat2048_long back to the plain string form

| File | Change | Why |
|---|---|---|
| [run_sets.yaml](../run_sets.yaml) | `convective_long` had three explicit folders (`output`, `particle_postprocess`, `particle_reduced`) under `Z:/...`. It is now `flat_2048x128x704/20261030_scalar2_long`, with the comment `lab PC D:/lbm_results (moved there 2026-11-02)` | The data now sits at `D:\lbm_results\flat_2048x128x704\20261030_scalar2_long\{output,particle_postprocess,particle_reduced}`. This is the standard `<lbm_results>/<case>/<date>_<tag>` layout, so no explicit folders are needed |

Setup on the lab PC: `local_paths.yaml` needs `lbm_results: D:/lbm_results`. The `particle_reduced` lookup tries `lbm_reduced` first, then `lbm_results`, so a lab PC `lbm_reduced` key does not break it.

To revert: `git revert d6dd4d7` (restores the `Z:` folders).

## What was deliberately left alone

The laptop (`Z:`) would now need its own run set, or the explicit-folder form again. None was added.

## How to check

```sh
pytest tests/test_run_sets.py
```
