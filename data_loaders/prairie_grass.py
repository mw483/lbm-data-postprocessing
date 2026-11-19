"""
Reader for the Project Prairie Grass (1956) files in validation_data/prairie_grass/.

Source: https://www.harmo.org/jsirwin/PrairieGrassDiscussion.html (J. S. Irwin's digitised copies of
Barad 1958, Vol. I-II, and Haugen 1959, Vol. III). SO2 released at 0.46 m (1.5 m in Exp 63-68), 10 min samples.

Files read here:
  PG_Horizontal sampling array concentration values.txt  (PGARCS.txt on the web page) arc concentrations at 1.5 m,
      ASTM D6589 format (D6589_UGDesign2_Table_2.pdf): per arc a header with experiment, arc number, date,
      time, nominal distance, then a line with receptor count, ..., release rate [g/s], release height,
      sampler height, unit multiplier; then rows "angle [deg], receptor, distance [m], concentration".
      Concentrations in mg/m^3 [U: the D6589 table says user units; PGVertConc.txt states mg/m^3 for the
      towers, and the arc values have the same size].
  PGrassTTUU.txt          20 min mean temperature [C] and wind speed [m/s] at 0.25-16 m; -999 = missing
  PGrassDaytimeZi.xls     daytime mixing heights [m] (Briggs 1978); -999 = missing; needs the xlrd package
  PGrassTABLE_5_4.TXT     SO2 evaporation correction factors per experiment and arc (not applied in the data files)
Experiments 70 and 71 in the met files are 35S and 48S.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ARCS_FILE = "PG_Horizontal sampling array concentration values.txt"
PROFILE_FILE = "PGrassTTUU.txt"
ZI_FILE = "PGrassDaytimeZi.xls"
CORRECTION_FILE = "PGrassTABLE_5_4.TXT"
MISSING = -999.0
_ARC_HEADER = re.compile(r"^\s*(\d+),\s*(\d+),'([^']*)','([^']*)',\s*([\d.]+)")


def read_arcs(folder):
    """Arc concentrations as one row per receptor: exp, arc, date, time, distance [m], q_gs [g/s],
    release_height, sampler_height, angle [deg], conc [mg/m^3, times the file's unit multiplier]."""
    rows, head, params = [], None, None
    with open(Path(folder) / ARCS_FILE, "r", encoding="latin-1") as f:
        lines = f.readlines()[1:]                      # line 1 is the title
    for line in lines:
        m = _ARC_HEADER.match(line)
        if m:
            head, params = m, None
            continue
        values = line.replace(",", " ").split()
        if head is not None and params is None:
            params = [float(v) for v in values]       # n, first, last, ixy, unit, xs, ys, q, hs, hr, mult
            continue
        if head is None or len(values) != 4:
            continue
        angle, _, distance, conc = (float(v) for v in values)
        rows.append({"exp": int(head[1]), "arc": int(head[2]), "date": head[3].strip(), "time": head[4].strip(),
                     "distance": distance, "q_gs": params[7], "release_height": params[8],
                     "sampler_height": params[9], "angle": angle, "conc": conc * params[10]})
    return pd.DataFrame(rows)


def crosswind_integrated(arcs):
    """Crosswind-integrated concentration per experiment and arc: C_y = sum C r dtheta [mg/m^2]
    (trapezoid over the receptors in angle order; the 360/0 degree wrap is unwrapped).
    Returns exp, distance, q_gs, cy, cy_over_q [s/m^2] (cy in g/m^2 divided by q in g/s)."""
    out = []
    for (exp, distance), g in arcs.groupby(["exp", "distance"]):
        angle = np.unwrap(np.deg2rad(g["angle"].to_numpy()))
        order = np.argsort(angle)
        conc = np.clip(g["conc"].to_numpy()[order], 0.0, None)
        cy = np.trapezoid(conc, angle[order]) * distance
        q = g["q_gs"].iloc[0]
        out.append({"exp": exp, "distance": distance, "q_gs": q, "cy": cy, "cy_over_q": cy * 1e-3 / q})
    return pd.DataFrame(out)


def read_profiles(folder):
    """Mean temperature [C] and wind [m/s] profiles: columns exp, z, temp, wind (missing values as NaN)."""
    rows, exp = [], None
    with open(Path(folder) / PROFILE_FILE, "r", encoding="latin-1") as f:
        for line in f:
            m = re.match(r"^\s*Exp\s+(\d+)", line)
            if m:
                exp = int(m[1])
                continue
            values = line.split()
            if exp is not None and len(values) == 3:
                try:
                    z, t, u = (float(v) for v in values)
                except ValueError:
                    continue
                rows.append({"exp": exp, "z": z, "temp": t, "wind": u})
    return pd.DataFrame(rows).replace(MISSING, np.nan)


def read_zi(folder):
    """Daytime mixing height per experiment: columns exp, zi [m] (NaN where missing)."""
    raw = pd.read_excel(Path(folder) / ZI_FILE, header=None)
    rows = []
    for exp, zi in raw.iloc[:, :2].itertuples(index=False):
        try:
            rows.append({"exp": int(exp), "zi": float(zi)})
        except (TypeError, ValueError):
            continue
    return pd.DataFrame(rows).replace(MISSING, np.nan)


def read_corrections(folder):
    """Evaporation correction factors: columns exp, distance, factor (missing blanks dropped)."""
    rows = []
    with open(Path(folder) / CORRECTION_FILE, "r", encoding="latin-1") as f:
        lines = f.readlines()
    arcs = None
    for line in lines:
        if line.strip().startswith("Exp"):
            arcs = [float(v) for v in line.split()[1:]]
            continue
        if arcs is None or not line.strip():
            continue
        # fixed-width columns: experiment, then one 9-character field per arc
        exp_field, rest = line[:8], line[8:]
        try:
            exp = int(exp_field)
        except ValueError:
            continue
        for i, d in enumerate(arcs):
            field = rest[i * 9:(i + 1) * 9].strip()
            if field:
                rows.append({"exp": exp, "distance": d, "factor": float(field)})
    return pd.DataFrame(rows)
