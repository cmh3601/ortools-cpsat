"""Unequal-area facility layout on a continuous (integer-grid) floor with CP-SAT.

Rectangular departments with optional 90-degree rotation are placed inside the
floor without overlapping each other or fixed obstacles (pillars, aisles,
docks). The objective is the flow-weighted rectilinear distance between
department centroids. Closeness requirements (max distance, "A" relations) and
separation requirements (min distance, "X" relations) are optional.

The hint / fix / relax options support CP + DRL hybrids: a policy proposes
positions (--hint-file), CP-SAT evaluates them (--fix-hint) or repairs and
improves only the departments the policy chose to free (--relax).

Usage:
    python layout_cpsat.py ../examples/layout_8.json --time-limit 30 --svg layout.svg
    python layout_cpsat.py ../examples/layout_8.json --hint-file policy.json --relax D2,D5
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ortools.sat.python import cp_model


def load(path: str | Path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    names = [f["name"] for f in spec["facilities"]]
    idx = {n: i for i, n in enumerate(names)}
    flows = spec.get("flows", [])
    if flows and isinstance(flows[0][0], str):
        flows = [[idx[a], idx[b], f] for a, b, f in flows]
    spec["flows"] = flows
    for key in ("adjacent", "separate"):
        spec[key] = [[idx[a], idx[b], d] if isinstance(a, str) else [a, b, d]
                     for a, b, d in spec.get(key, [])]
    return spec


def build_model(spec: dict, flow_scale: int = 1, hint: dict | None = None,
                relax: set[str] | None = None, break_symmetry: bool = True):
    W, H = spec["floor"]["width"], spec["floor"]["height"]
    gap = spec.get("min_gap", 0)
    fac = spec["facilities"]
    model = cp_model.CpModel()
    x, y, wd, ht, rot, xs, ys = [], [], [], [], [], [], []
    for f in fac:
        w0, h0 = f["w"], f["h"]
        r = model.new_bool_var(f"rot_{f['name']}") if f.get("rotatable", False) and w0 != h0 else None
        if r is None:
            wv, hv = model.new_constant(w0), model.new_constant(h0)
        else:
            wv = model.new_int_var(min(w0, h0), max(w0, h0), f"w_{f['name']}")
            hv = model.new_int_var(min(w0, h0), max(w0, h0), f"h_{f['name']}")
            model.add(wv == w0 + (h0 - w0) * r)
            model.add(hv == h0 + (w0 - h0) * r)
        xi = model.new_int_var(0, W, f"x_{f['name']}")
        yi = model.new_int_var(0, H, f"y_{f['name']}")
        model.add(xi + wv <= W)
        model.add(yi + hv <= H)
        # Clearance: inflate every rectangle by `gap` to the right/top, and the floor too.
        xe = model.new_int_var(0, W + gap, f"xe_{f['name']}")
        ye = model.new_int_var(0, H + gap, f"ye_{f['name']}")
        xs.append(model.new_interval_var(xi, wv + gap, xe, f"xi_{f['name']}"))
        ys.append(model.new_interval_var(yi, hv + gap, ye, f"yi_{f['name']}"))
        x.append(xi), y.append(yi), wd.append(wv), ht.append(hv), rot.append(r)
    for k, ob in enumerate(spec.get("obstacles", [])):
        xs.append(model.new_fixed_size_interval_var(ob["x"], ob["w"] + gap, f"ox_{k}"))
        ys.append(model.new_fixed_size_interval_var(ob["y"], ob["h"] + gap, f"oy_{k}"))
    model.add_no_overlap_2d(xs, ys)

    # Doubled centroids keep everything integral: 2*cx = 2x + w.
    cx = [model.new_int_var(0, 2 * W, f"cx_{f['name']}") for f in fac]
    cy = [model.new_int_var(0, 2 * H, f"cy_{f['name']}") for f in fac]
    for i in range(len(fac)):
        model.add(cx[i] == 2 * x[i] + wd[i])
        model.add(cy[i] == 2 * y[i] + ht[i])

    pair_dist = {}

    def dist(i: int, j: int):
        key = (min(i, j), max(i, j))
        if key not in pair_dist:
            dx = model.new_int_var(0, 2 * W, f"dx_{key}")
            dy = model.new_int_var(0, 2 * H, f"dy_{key}")
            model.add_abs_equality(dx, cx[i] - cx[j])
            model.add_abs_equality(dy, cy[i] - cy[j])
            pair_dist[key] = dx + dy
        return pair_dist[key]

    terms = []
    for i, j, f in spec["flows"]:
        wgt = int(round(f * flow_scale))
        if wgt:
            terms.append(wgt * dist(i, j))
    # Doubled distances are integers, so floor/ceil of the doubled thresholds is exact.
    for i, j, dmax in spec.get("adjacent", []):
        model.add(dist(i, j) <= math.floor(2 * dmax))
    for i, j, dmin in spec.get("separate", []):
        model.add(dist(i, j) >= math.ceil(2 * dmin))
    model.minimize(sum(terms))

    fixed = spec.get("fixed", {})
    names = [f["name"] for f in fac]
    for n, pos in fixed.items():
        i = names.index(n)
        model.add(x[i] == pos[0])
        model.add(y[i] == pos[1])
    # Mirror symmetry: valid only when the instance is symmetric (no obstacles, fixed
    # positions or a partial relax neighbourhood). Puts department 0's centroid in the
    # lower-left quadrant.
    if break_symmetry and not fixed and not spec.get("obstacles") and relax is None:
        model.add(cx[0] <= W)
        model.add(cy[0] <= H)

    if hint:
        for i, n in enumerate(names):
            if n in hint:
                hx, hy, *hr = hint[n]
                model.add_hint(x[i], hx)
                model.add_hint(y[i], hy)
                if rot[i] is not None:
                    model.add_hint(rot[i], bool(hr[0]) if hr else False)
                if relax is not None and n not in relax:
                    model.add(x[i] == hx)
                    model.add(y[i] == hy)
                    if rot[i] is not None:
                        model.add(rot[i] == (bool(hr[0]) if hr else False))
    return model, {"x": x, "y": y, "w": wd, "h": ht, "rot": rot}


def extract(solver: cp_model.CpSolver, spec: dict, v: dict) -> dict:
    out = {}
    for i, f in enumerate(spec["facilities"]):
        r = v["rot"][i]
        out[f["name"]] = {"x": solver.value(v["x"][i]), "y": solver.value(v["y"][i]),
                          "w": solver.value(v["w"][i]), "h": solver.value(v["h"][i]),
                          "rotated": bool(solver.value(r)) if r is not None else False}
    return out


def validate(spec: dict, placement: dict) -> float:
    """Independent check of a placement; returns the flow-weighted centroid distance."""
    W, H = spec["floor"]["width"], spec["floor"]["height"]
    gap = spec.get("min_gap", 0)
    rects = []
    for f in spec["facilities"]:
        p = placement[f["name"]]
        assert {p["w"], p["h"]} == {f["w"], f["h"]}, f"{f['name']} has wrong dimensions"
        assert 0 <= p["x"] and p["x"] + p["w"] <= W and 0 <= p["y"] and p["y"] + p["h"] <= H, \
            f"{f['name']} leaves the floor"
        rects.append((f["name"], p["x"], p["y"], p["w"], p["h"]))
    for ob in spec.get("obstacles", []):
        rects.append(("obstacle", ob["x"], ob["y"], ob["w"], ob["h"]))
    for a in range(len(rects)):
        for b in range(a + 1, len(rects)):
            na, xa, ya, wa, ha = rects[a]
            nb, xb, yb, wb, hb = rects[b]
            apart = (xa + wa + gap <= xb or xb + wb + gap <= xa or
                     ya + ha + gap <= yb or yb + hb + gap <= ya)
            assert apart, f"{na} overlaps {nb}"
    names = [f["name"] for f in spec["facilities"]]

    def c(n):
        p = placement[n]
        return p["x"] + p["w"] / 2, p["y"] + p["h"] / 2

    def d(i, j):
        (xi, yi), (xj, yj) = c(names[i]), c(names[j])
        return abs(xi - xj) + abs(yi - yj)

    for i, j, dmax in spec.get("adjacent", []):
        assert d(i, j) <= dmax + 1e-9, f"{names[i]}-{names[j]} farther than {dmax}"
    for i, j, dmin in spec.get("separate", []):
        assert d(i, j) >= dmin - 1e-9, f"{names[i]}-{names[j]} closer than {dmin}"
    return float(sum(f * d(i, j) for i, j, f in spec["flows"]))


def write_svg(spec: dict, placement: dict, path: Path, scale: int = 20) -> None:
    W, H = spec["floor"]["width"], spec["floor"]["height"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * scale}" height="{H * scale}" '
             f'viewBox="0 0 {W * scale} {H * scale}" font-family="sans-serif" font-size="12">',
             f'<rect width="{W * scale}" height="{H * scale}" fill="#fff" stroke="#000"/>']
    for ob in spec.get("obstacles", []):
        parts.append(f'<rect x="{ob["x"] * scale}" y="{(H - ob["y"] - ob["h"]) * scale}" '
                     f'width="{ob["w"] * scale}" height="{ob["h"] * scale}" fill="#999"/>')
    for n, p in placement.items():
        px, py = p["x"] * scale, (H - p["y"] - p["h"]) * scale
        parts.append(f'<rect x="{px}" y="{py}" width="{p["w"] * scale}" height="{p["h"] * scale}" '
                     f'fill="#cfe3f7" stroke="#1f4e79"/>')
        parts.append(f'<text x="{px + p["w"] * scale / 2}" y="{py + p["h"] * scale / 2}" '
                     f'text-anchor="middle" dominant-baseline="middle">{n}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("--time-limit", type=float, default=30.0)
    ap.add_argument("--deterministic-time", type=float)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--flow-scale", type=int, default=1, help="multiply flows before rounding to integers")
    ap.add_argument("--hint-file", type=Path, help='JSON {"D1": [x, y, rotated], ...}')
    ap.add_argument("--fix-hint", action="store_true", help="evaluate the hinted layout only")
    ap.add_argument("--relax", help="comma-separated departments to free; others fixed at the hint")
    ap.add_argument("--no-symmetry-breaking", action="store_true")
    ap.add_argument("--svg", type=Path)
    ap.add_argument("--log", action="store_true")
    args = ap.parse_args()

    spec = load(args.instance)
    hint = json.loads(args.hint_file.read_text()) if args.hint_file else None
    relax = set(args.relax.split(",")) if args.relax else None
    if relax is not None and hint is None:
        ap.error("--relax needs --hint-file")
    model, v = build_model(spec, args.flow_scale, hint, relax, not args.no_symmetry_breaking)
    solver = cp_model.CpSolver()
    p = solver.parameters
    p.max_time_in_seconds = args.time_limit
    p.num_workers = args.workers
    p.random_seed = args.seed
    p.log_search_progress = args.log
    if args.deterministic_time is not None:
        p.max_deterministic_time = args.deterministic_time
    if args.fix_hint:
        p.fix_variables_to_their_hinted_value = True
    status = solver.solve(model)
    out = {"status": solver.status_name(status), "wall_time_s": round(solver.wall_time, 3)}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        placement = extract(solver, spec, v)
        # Model objective uses doubled centroids and scaled flows.
        out["objective"] = solver.objective_value / (2 * args.flow_scale)
        out["best_bound"] = solver.best_objective_bound / (2 * args.flow_scale)
        out["validated_objective"] = validate(spec, placement)
        out["placement"] = placement
        if args.svg:
            write_svg(spec, placement, args.svg)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
