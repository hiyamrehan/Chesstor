"""Turn results/*.json into a LaTeX longtable (so report tables are generated from raw results)."""
import json
import sys
from pathlib import Path

COND = {
    "A_random_normal": "A. Random games, normal light (10 games, seed 200)",
    "B_random_dim": "B. Random games, dim light (seed 201)",
    "C_random_glare": "C. Random games, glare (seed 202)",
    "D_special_normal": "D. Special-move games, normal (18 games, seed 203)",
    "E_special_dim": "E. Special-move games, dim (seed 204)",
    "F_special_persist2": "F. Special moves, 2\\% persistent errors (seed 205)",
    "G_random_persist3": "G. Random games, 3\\% persistent errors (seed 206)",
    "H_special_stress": "H. Special moves, 8\\% frame error + 30\\% mask miss (seed 207)",
}
src, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = [r"\begin{longtable}{p{0.27\textwidth}rrrr}", r"\toprule",
        r"System & Move acc. & False conf./100 & Desync & Median lat. (s)\\ \midrule", r"\endhead"]
for key, title in COND.items():
    res = json.loads((src / f"{key}.json").read_text())
    rows.append(rf"\multicolumn{{5}}{{l}}{{\textbf{{{title}}}}}\\")
    for name, r in res.items():
        lat = "--" if r["median_latency_s"] is None else f"{r['median_latency_s']:.2f}"
        nm = name.replace("&", r"\&")
        fc = r["false_confirmations_per_100_moves"]
        rows.append(rf"{nm} & {r['move_accuracy']:.3f} & {fc:.1f} & {r['desync_rate']:.2f} & {lat}\\")
    rows.append(r"\midrule")
rows += [r"\bottomrule", r"\end{longtable}"]
out.write_text("\n".join(rows) + "\n")
