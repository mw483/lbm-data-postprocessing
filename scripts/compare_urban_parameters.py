"""
Compare the urban morphology of several maps: idealised cube arrays, boxes cut
from real map sets (e.g. the Jakarta candidates), whole LBM-city cases.

    python scripts/compare_urban_parameters.py config.yaml [--out FOLDER]

Config (YAML), one entry per map, all on the same cell size:

    dx: 2.0                          # m per cell
    arrangement: staggered           # Macdonald coefficients for real maps (default staggered)
    entries:
      - name: cubes aligned
        type: cubes
        arrangement: aligned         # aligned | staggered (every other row shifted half a pitch in j)
        domain_cells: [512, 128]     # n_i (wind direction), n_j
        size_cells: 16               # footprint side
        height_cells: 16             # height = height_cells x dx
        gap_cells: [16, 16]          # gap along i, along j
        nz: 160                      # optional: domain top for top/H_max and blockage
      - name: Jakarta J1
        type: map
        folder: F:/TSUBAME4_12m/map  # topography.dat, building.dat, vegetation.dat
        box: [i0, i1, j0, j1]        # optional, end exclusive; or:
        candidates: path/to/candidates.yaml
        box_name: J1
        nz: 160
      - name: flat case
        type: case                   # <lbm_cases>/<case>/map from local_paths.yaml
        case: flat_512x128x1024

Outputs in --out (default <figures>/urban_parameters/<config file name>/):
- urban_parameters.csv: one row per parameter, one column per entry.
- urban_parameters.png, explained:
  1. What: (a) the dimensionless shape numbers of each map side by side,
     (b) how the building volume is spread over heights, (c) each map from above.
  2. Why: purpose = justify which maps to simulate and show how real
     neighbourhoods differ from the idealised cube arrays used in the
     literature and our earlier runs. λp and λf set the drag; σ_H/H and
     H_max/H say how mixed the heights are (they change drag and roughness,
     Kanda et al. 2013); H/W sets the street-canyon flow regime (Oke 1988:
     isolated roughness < ~0.3, wake interference ~0.3-0.65, skimming > ~0.65 [U]);
     d/H and z0/H are what a meteorological model would use for this surface.
  3. Reference: aligned cubes with gap = side have λp = λf = 0.25 (Coceal et
     al. 2006, J. Wind Eng. Ind. Aerodyn. / BLM); d and z0 from Macdonald et al.
     (1998) and Kanda et al. (2013) [U: coefficients to check against the papers].
  4. Units: heights in m above ground; d/H and z0/H divided by the mean building
     height of that map; whole map or box, wind along +i (map x).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from data_loaders.map_io import load_map_set
from physics_core.urban_morphology import (blockage_by_column, cube_array, morphology_parameters,
                                           object_heights)

# =============================================================================
# Settings
# =============================================================================
BAR_PARAMS = [("lambda_p", "λp"), ("lambda_f_x", "λf (x)"), ("sigma_H_over_H_mean", "σ_H / H"),
              ("H_over_W_x", "H / W (x)"), ("d_macdonald_over_H", "d/H Macdonald"),
              ("d_kanda_over_H", "d/H Kanda"), ("z0_macdonald_over_H", "z0/H Macdonald"),
              ("z0_kanda_over_H", "z0/H Kanda")]
COLORS = ["#2f6db5", "#e08a2c", "#3a9e5f", "#c0392b", "#7b5ea7", "#8a8a8a", "#d4a017", "#17a2b8"]
INK, MUTED = "#333333", "#8a8a8a"


# =============================================================================
# Building the maps
# =============================================================================
def candidate_box(path, name):
    with open(path, "r", encoding="utf-8") as f:
        cands = (yaml.safe_load(f) or {}).get("candidates", [])
    for c in cands:
        if str(c["name"]) == str(name):
            return [int(v) for v in c["box"]]
    raise SystemExit(f"[ERROR] no candidate {name!r} in {path}")


_MAP_CACHE = {}


def load_heights(folder):
    """Building and tree heights above ground of a map set (cached: several boxes of one map load it once)."""
    key = str(Path(folder).resolve())
    if key not in _MAP_CACHE:
        maps = load_map_set(folder)
        _MAP_CACHE[key] = (*object_heights(maps), maps["topo"])
    return _MAP_CACHE[key]


def entry_heights(e, cfg_dir):
    """(building heights above ground, ground, description) of one config entry."""
    kind = e.get("type")
    if kind == "cubes":
        n_i, n_j = e["domain_cells"]
        gi, gj = e["gap_cells"]
        hb = cube_array(n_i, n_j, e["size_cells"], e["height_cells"] * DX, gi, gj, e.get("arrangement", "aligned"))
        return hb, np.zeros_like(hb), f"{e.get('arrangement', 'aligned')} cubes {e['size_cells']} cells"
    if kind in ("map", "case"):
        if kind == "case":
            from data_loaders.local_paths import case_map_dir, load_local_paths
            folder = case_map_dir(load_local_paths(), e["case"])
        else:
            folder = Path(e["folder"])
            if not folder.is_absolute():
                folder = cfg_dir / folder
        hb, _, topo = load_heights(folder)
        box = e.get("box")
        if box is None and e.get("box_name"):
            cand = Path(e["candidates"])
            box = candidate_box(cand if cand.is_absolute() else cfg_dir / cand, e["box_name"])
        if box is not None:
            i0, i1, j0, j1 = (int(v) for v in box)
            hb, topo = hb[j0:j1, i0:i1], topo[j0:j1, i0:i1]
        return hb, topo, f"{folder}" + (f" box {list(box)}" if box is not None else "")
    raise SystemExit(f"[ERROR] entry {e.get('name')!r}: type must be cubes, map or case")


def entry_parameters(e, hb, topo, default_arrangement):
    arr = e.get("arrangement", default_arrangement)
    p = morphology_parameters(hb, DX, arrangement=arr)
    p["ground_range_m"] = float(topo.max() - topo.min())
    if e.get("nz"):
        top = e["nz"] * DX
        blk = blockage_by_column(hb, top, DX)
        p.update({"nz": int(e["nz"]), "top_m": top,
                  "top_over_H_max": top / p["H_max_m"] if p["H_max_m"] else np.inf,
                  "length_over_H_max": p["length_x_m"] / p["H_max_m"] if p["H_max_m"] else np.inf,
                  "blockage_max": float(blk.max()), "blockage_mean": float(blk.mean())})
    return p


# =============================================================================
# Figure
# =============================================================================
def plot(names, params, heights, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                         "font.size": 9})
    n = len(names)
    aspect = max(h.shape[0] / h.shape[1] for h in heights)
    view_h = max(1.2, 13 * aspect)
    fig = plt.figure(figsize=(14, 5 + view_h * n))
    gs = fig.add_gridspec(1 + n, 2, height_ratios=[5.0] + [view_h] * n, width_ratios=[1.6, 1],
                          hspace=0.45, wspace=0.18)

    ax = fig.add_subplot(gs[0, 0])
    x = np.arange(len(BAR_PARAMS))
    w = 0.8 / n
    for k, name in enumerate(names):
        vals = [params[k].get(key, np.nan) for key, _ in BAR_PARAMS]
        ax.bar(x + (k - (n - 1) / 2) * w, vals, w, color=COLORS[k % len(COLORS)], label=name)
    ax.set_xticks(x, [lab for _, lab in BAR_PARAMS], rotation=20, ha="right")
    ax.set_ylabel("value [-]")
    ax.grid(axis="y", color="#e6e6e6", lw=0.6)
    ax.legend(frameon=False, fontsize=8, ncol=min(n, 3))
    ax.set_title("(a) shape numbers (wind along x; H = mean building height of each map)", loc="left", fontsize=9)

    ax2 = fig.add_subplot(gs[0, 1])
    hmax = max(float(h.max()) for h in heights) or 1.0
    edges = np.arange(0, hmax + 2 * DX, DX)
    for k, (name, hb) in enumerate(zip(names, heights)):
        h = hb[hb > 0]
        if h.size:
            vol, _ = np.histogram(h, bins=edges, weights=h)
            ax2.step(edges[:-1], vol / vol.sum(), where="post", color=COLORS[k % len(COLORS)], label=name)
    ax2.set_xlabel("building height above ground [m]")
    ax2.set_ylabel("share of building volume")
    ax2.grid(color="#e6e6e6", lw=0.6)
    ax2.legend(frameon=False, fontsize=8)
    ax2.set_title("(b) building volume by height (2 m bins; equal arrays overlap)", loc="left", fontsize=9)

    vmax = max(1.0, hmax)
    for k, (name, hb) in enumerate(zip(names, heights)):
        a = fig.add_subplot(gs[1 + k, :])
        im = a.imshow(np.where(hb > 0, hb, np.nan), origin="lower", cmap="viridis", vmin=0, vmax=vmax,
                      interpolation="nearest", aspect="equal")
        a.set_title(f"(c) {name}: from above, {hb.shape[1]} x {hb.shape[0]} cells", loc="left", fontsize=9)
        if k == n - 1:
            a.set_xlabel("column i (wind direction)")
        a.set_ylabel("row j")
        fig.colorbar(im, ax=a, label="height [m]", fraction=0.025, pad=0.01)
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_png}")


# =============================================================================
# Main
# =============================================================================
def main():
    global DX
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="YAML file with the entries")
    ap.add_argument("--out", help="output folder")
    args = ap.parse_args()
    cfg_path = Path(args.config)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    DX = float(cfg.get("dx", 2.0))
    default_arr = cfg.get("arrangement", "staggered")
    if args.out:
        out = Path(args.out)
    else:
        try:
            from data_loaders.local_paths import load_local_paths
            out = load_local_paths()["figures"] / "urban_parameters" / cfg_path.stem
        except (FileNotFoundError, KeyError):
            out = Path.cwd() / "urban_parameters" / cfg_path.stem
    out.mkdir(parents=True, exist_ok=True)

    names, params, heights, about = [], [], [], []
    for e in cfg["entries"]:
        hb, topo, desc = entry_heights(e, cfg_path.parent)
        names.append(str(e["name"]))
        params.append(entry_parameters(e, hb, topo, default_arr))
        heights.append(hb)
        about.append(desc)
        print(f"{e['name']}: {desc}")

    table = pd.DataFrame(params, index=names).T
    table.loc["source"] = about
    table.to_csv(out / "urban_parameters.csv", index_label="parameter")
    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.float_format", "{:.4g}".format):
        print(table.drop(index="source").to_string())
    print(f"Saved {out / 'urban_parameters.csv'}")
    plot(names, params, heights, out / "urban_parameters.png")


DX = 2.0

if __name__ == "__main__":
    main()
