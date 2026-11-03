"""Job-shop scheduling with OR-Tools CP-SAT.

Shows the core scheduling pattern (interval variables, precedences,
no-overlap per machine, makespan objective), warm starts from a dispatching
rule or from an external policy such as a DRL agent, reproducible solver
settings, and an independent validator for the returned schedule.

Usage:
    python jobshop_cpsat.py ../data/ft06.txt --time-limit 10 --workers 8 --seed 0
    python jobshop_cpsat.py ../data/ft06.txt --hint spt
    python jobshop_cpsat.py ../data/ft06.txt --hint-file starts.json   # {"starts": [[...], ...]}
    python jobshop_cpsat.py ../data/ft06.txt --hint spt --fix-hint     # evaluate the hint only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ortools.sat.python import cp_model

Job = list[tuple[int, int]]  # [(machine, duration), ...] in route order


def read_orlib(path: str | Path) -> list[Job]:
    rows = [ln.split() for ln in Path(path).read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    n_jobs, n_machines = int(rows[0][0]), int(rows[0][1])
    jobs = []
    for r in rows[1:1 + n_jobs]:
        vals = list(map(int, r))
        job = list(zip(vals[0::2], vals[1::2]))
        if len(job) != n_machines:
            raise ValueError(f"Expected {n_machines} operations per job, got {len(job)}.")
        jobs.append(job)
    return jobs


def dispatch_schedule(jobs: list[Job], rule: str = "spt") -> list[list[int]]:
    """Feasible schedule by list scheduling: repeatedly start the operation with the
    earliest possible start; break ties with the rule (spt, lpt, mwkr, fifo)."""
    next_op = [0] * len(jobs)
    job_ready = [0] * len(jobs)
    mach_ready: dict[int, int] = {}
    starts = [[0] * len(job) for job in jobs]
    remaining = [sum(d for _, d in job) for job in jobs]
    for _ in range(sum(len(j) for j in jobs)):
        cands = []
        for j, job in enumerate(jobs):
            if next_op[j] < len(job):
                m, d = job[next_op[j]]
                est = max(job_ready[j], mach_ready.get(m, 0))
                key = {"spt": d, "lpt": -d, "mwkr": -remaining[j], "fifo": j}[rule]
                cands.append((est, key, j))
        est, _, j = min(cands)
        m, d = jobs[j][next_op[j]]
        starts[j][next_op[j]] = est
        job_ready[j] = mach_ready[m] = est + d
        remaining[j] -= d
        next_op[j] += 1
    return starts


def validate(jobs: list[Job], starts: list[list[int]]) -> int:
    """Raise AssertionError on any violated constraint; return the makespan."""
    by_machine: dict[int, list[tuple[int, int]]] = {}
    for j, job in enumerate(jobs):
        for k, (m, d) in enumerate(job):
            s = starts[j][k]
            assert s >= 0, f"job {j} op {k} starts before 0"
            if k > 0:
                assert s >= starts[j][k - 1] + job[k - 1][1], f"precedence violated in job {j} op {k}"
            by_machine.setdefault(m, []).append((s, s + d))
    for m, ivs in by_machine.items():
        ivs.sort()
        for (s1, e1), (s2, _) in zip(ivs, ivs[1:]):
            assert e1 <= s2, f"overlap on machine {m}: [{s1},{e1}) and [{s2},...)"
    return max(starts[j][-1] + job[-1][1] for j, job in enumerate(jobs))


def build_model(jobs: list[Job], hint: list[list[int]] | None = None):
    model = cp_model.CpModel()
    horizon = sum(d for job in jobs for _, d in job)
    start, end, by_machine = {}, {}, {}
    for j, job in enumerate(jobs):
        for k, (m, d) in enumerate(job):
            s = model.new_int_var(0, horizon, f"s_{j}_{k}")
            e = model.new_int_var(0, horizon, f"e_{j}_{k}")
            iv = model.new_interval_var(s, d, e, f"iv_{j}_{k}")
            start[j, k], end[j, k] = s, e
            by_machine.setdefault(m, []).append(iv)
            if k > 0:
                model.add(s >= end[j, k - 1])
    for ivs in by_machine.values():
        model.add_no_overlap(ivs)
    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, [end[j, len(job) - 1] for j, job in enumerate(jobs)])
    model.minimize(makespan)
    if hint is not None:
        for j, job in enumerate(jobs):
            for k, (_, d) in enumerate(job):
                model.add_hint(start[j, k], hint[j][k])
                model.add_hint(end[j, k], hint[j][k] + d)
        model.add_hint(makespan, validate(jobs, hint))
    return model, start, makespan


def solve(model: cp_model.CpModel, time_limit: float = 10.0, workers: int = 8, seed: int = 0,
          deterministic_time: float | None = None, fix_hint: bool = False, log: bool = False):
    solver = cp_model.CpSolver()
    p = solver.parameters
    p.max_time_in_seconds = time_limit
    p.num_workers = workers
    p.random_seed = seed
    p.log_search_progress = log
    if deterministic_time is not None:
        p.max_deterministic_time = deterministic_time  # reproducible budget, independent of machine load
    if fix_hint:
        p.fix_variables_to_their_hinted_value = True
    status = solver.solve(model)
    return solver, status


def report(solver: cp_model.CpSolver, status) -> dict:
    out = {"status": solver.status_name(status), "wall_time_s": round(solver.wall_time, 3)}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        obj, bound = solver.objective_value, solver.best_objective_bound
        out.update({"objective": obj, "best_bound": bound,
                    "gap": 0.0 if obj == 0 else abs(obj - bound) / abs(obj)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("--time-limit", type=float, default=10.0)
    ap.add_argument("--deterministic-time", type=float)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hint", choices=["spt", "lpt", "mwkr", "fifo"])
    ap.add_argument("--hint-file", type=Path, help='JSON {"starts": [[...], ...]} from any external policy')
    ap.add_argument("--fix-hint", action="store_true", help="evaluate the hint instead of optimising")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    jobs = read_orlib(args.instance)
    hint = None
    info: dict = {"instance": str(args.instance), "jobs": len(jobs), "machines": len(jobs[0])}
    if args.hint:
        hint = dispatch_schedule(jobs, args.hint)
    elif args.hint_file:
        hint = json.loads(args.hint_file.read_text())["starts"]
    if hint is not None:
        info["hint_makespan"] = validate(jobs, hint)
    model, start, _ = build_model(jobs, hint)
    solver, status = solve(model, args.time_limit, args.workers, args.seed, args.deterministic_time,
                           args.fix_hint, args.log)
    info.update(report(solver, status))
    if args.fix_hint:
        info["note"] = "variables fixed to the hint: OPTIMAL/bound refer to the fixed model, not the instance"
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        starts = [[solver.value(start[j, k]) for k in range(len(job))] for j, job in enumerate(jobs)]
        info["validated_makespan"] = validate(jobs, starts)
        info["starts"] = starts
    text = json.dumps(info, indent=2)
    if args.out:
        args.out.write_text(text)
    print(text if not args.out else f"wrote {args.out}")


if __name__ == "__main__":
    main()
