# x-z heatmaps: no combined output for a one-run set (2026-11-02)

**Commits**: `3ce8676` (branch `analysis/scalar2-outputs`)

**Goal**: Mikael asked that `plot_xz_yav_heatmaps.py` not write the combined output when the run set has only one run (for example `flat2048_long`), because it repeats the per-case frames.

**Result**: Ran the script end to end on a one-run test set (the real 512 convective wind output): 7 windows x 4 variables, no combined files written. Not checked: a two-run set after the change (that code path is unchanged).

## Commit 3ce8676: combined frames only for more than one run

| File | Change | Why |
|---|---|---|
| [scripts/plot_xz_yav_heatmaps.py](../scripts/plot_xz_yav_heatmaps.py) | `combined_step*.png`, `combined.gif` and `combined.mp4` are written only when `len(runs) > 1` (new flag `combine`). Per-case frames, per-case GIF/MP4 and the shared colour scale are unchanged | With one run the combined frame shows the same panel as `<case>_step*.png` |
| [README.md](../README.md) | The heatmap sentence now says the combined frames and `combined.gif` exist only for sets with more than one run | Keep the docs in line with the script |

To revert: `git revert 3ce8676`.

## How to check

```sh
python scripts/plot_xz_yav_heatmaps.py --set flat2048_long   # no combined_* files
```
