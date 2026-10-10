#!/usr/bin/env python3
"""Read the minutes of workflow runs, per stage, and the minutes of the coordinator.

    minutes.py RECORD.json [RECORD.json ...] [--transcript MAIN.jsonl --until ISO8601]

A run record is the file that the harness writes when a workflow run ends. A stage is a phase
title: the run records given are merged by stage. An agent is finished when its state is "done".

    wall_minutes        the length of the union of the intervals of the finished agents
    agent_minutes       the sum of the durations of the finished agents
    unfinished_minutes  for the agents that did not finish, the end of their run minus their start

Stages overlap, so their wall minutes must not be added up: `total` is the union over every
finished agent.

With --transcript, the transcript of the main session, and --until, a date with an offset or Z,
`coordinator` holds two bounds of the coordinator's work in the window from the earliest start of
the runs to --until. `model_minutes` is the time that the model of the main session spent
producing output: a lower bound, which leaves out every tool call. `turn_minutes` is the length of
its turns: an upper bound, which includes every wait inside a turn.

The script reads the identifier, the status, the times and the phase titles of a run record, and
the type, the time and the turn markers of a transcript record. It prints no other text of them,
and an error names a path and a rule, never a value.

Exit 0: the report, one JSON object on standard output.
Exit 2: the script could not do its job, or the call was wrong; standard output is empty.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
TYPE_NAMES = {int: "an integer", str: "a string", list: "a list", dict: "an object"}


class Failure(Exception):
    """The script cannot do its job: status 2, and one line on standard error."""


def typed(value, kind: type, path: str):
    """`value`, when it has the type that the harness writes at `path`. A bool is not an integer."""
    if not isinstance(value, kind) or isinstance(value, bool):
        raise Failure(f"{path}: missing, or not {TYPE_NAMES[kind]}")
    return value


def instant(text) -> int | None:
    """The milliseconds since the epoch of an ISO 8601 date with an offset or Z; None for any other."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if moment.utcoffset() is None:
        return None
    return (moment - EPOCH) // timedelta(milliseconds=1)


def minutes(milliseconds: int) -> float:
    """Minutes with one decimal. Figures are added in whole milliseconds and converted once, here."""
    return round(milliseconds / 60000, 1)


def total(intervals) -> int:
    """The sum of the lengths of intervals, each a start and an end."""
    return sum(end - start for start, end in intervals)


def union(intervals) -> int:
    """The length of the union of intervals; one that ends before it starts counts for nothing."""
    length, reached = 0, float("-inf")
    for start, end in sorted(intervals):
        start = max(start, reached)
        if end > start:
            length += end - start
            reached = end
    return length


def run_of(data: bytes) -> dict:
    """A run record, reduced to what the report reads. A failure names the key that is wrong.

    An agent has the title of its phase, its start and, when it is done, its end; the end of an
    agent that did not finish is None.
    """
    try:
        record = typed(json.loads(data), dict, "the run record")
    except (ValueError, RecursionError):
        # RecursionError: lists or objects nested deeper than Python reads.
        raise Failure("not JSON") from None
    start = typed(record.get("startTime"), int, "startTime")
    try:
        started_at = (EPOCH + timedelta(milliseconds=start)).replace(tzinfo=None)
    except OverflowError:
        raise Failure("startTime: not a date") from None
    run = {
        "run_id": typed(record.get("runId"), str, "runId"),
        "status": typed(record.get("status"), str, "status"),
        "started_at": started_at.isoformat(timespec="seconds") + "Z",
        "start": start,
        "end": start + typed(record.get("durationMs"), int, "durationMs"),
        "phases": [],
        "agents": [],
    }
    for index, entry in enumerate(typed(record.get("workflowProgress"), list, "workflowProgress")):
        path = f"workflowProgress[{index}]"
        kind = typed(typed(entry, dict, path).get("type"), str, f"{path}.type")
        if kind == "workflow_phase":
            run["phases"].append(typed(entry.get("title"), str, f"{path}.title"))
        elif kind == "workflow_agent":
            agent = {
                "stage": typed(entry.get("phaseTitle"), str, f"{path}.phaseTitle"),
                "start": typed(entry.get("startedAt"), int, f"{path}.startedAt"),
                "end": None,
            }
            if typed(entry.get("state"), str, f"{path}.state") == "done":
                duration = typed(entry.get("durationMs"), int, f"{path}.durationMs")
                agent["end"] = agent["start"] + duration
            run["agents"].append(agent)
    return run


def report(runs: list[dict]) -> dict:
    """The runs in order of start, the minutes of each stage, and the total.

    Stages are in order of the earliest start of any of their agents; those with no agent come
    last, in the order in which they were first declared.
    """
    runs = sorted(runs, key=lambda run: (run["start"], run["run_id"]))
    if len({run["run_id"] for run in runs}) < len(runs):
        raise Failure("runId: the same run is given twice")
    stages, finished = {}, []
    for run in runs:
        for title in run["phases"] + [agent["stage"] for agent in run["agents"]]:
            stages.setdefault(title, {"finished": [], "unfinished": [], "first_start": float("inf")})
        for agent in run["agents"]:
            stage = stages[agent["stage"]]
            stage["first_start"] = min(stage["first_start"], agent["start"])
            if agent["end"] is None:
                stage["unfinished"].append((agent["start"], run["end"]))
            else:
                stage["finished"].append((agent["start"], agent["end"]))
                finished.append((agent["start"], agent["end"]))
    return {
        "runs": [
            {
                "run_id": run["run_id"],
                "status": run["status"],
                "started_at": run["started_at"],
                "minutes": minutes(run["end"] - run["start"]),
            }
            for run in runs
        ],
        "stages": [
            {
                "stage": title,
                "agents": len(stage["finished"]),
                "wall_minutes": minutes(union(stage["finished"])),
                "agent_minutes": minutes(total(stage["finished"])),
                "unfinished": len(stage["unfinished"]),
                "unfinished_minutes": minutes(total(stage["unfinished"])),
            }
            for title, stage in sorted(stages.items(), key=lambda item: item[1]["first_start"])
        ],
        "total": {
            "wall_minutes": minutes(union(finished)),
            "agent_minutes": minutes(total(finished)),
        },
    }


def records_of(data: bytes) -> list[dict]:
    """The records of a transcript, one JSON object on each line.

    A last line that does not parse is left out: the session may be writing it.
    """
    lines = data.splitlines()
    records = []
    for number, line in enumerate(lines, 1):
        try:
            records.append(typed(json.loads(line), dict, f"line {number}"))
        except (ValueError, RecursionError):
            if number < len(lines):
                raise Failure(f"line {number}: not JSON") from None
    return records


def timeline_of(records: list[dict]) -> list[tuple[int, int, str]]:
    """The events and the stop records of a main transcript, each a time, a line and a kind.

    An event is a record of type user or assistant that has a timestamp and is not a sidechain
    record. Its kind is its type, or "start" when it has the key turnOrigin. A "stop" is the system
    record that ends a turn. They are in order of time, and of line where the times are equal.
    Records of type user or assistant are a failure when none of them starts a turn, whether or not
    they are events.
    """
    timeline = []
    for number, record in enumerate(records, 1):
        kind = record.get("type")
        stop = kind == "system" and record.get("subtype") == "stop_hook_summary"
        event = kind in ("user", "assistant") and not record.get("isSidechain")
        if not (stop or event) or "timestamp" not in record:
            continue
        time = instant(record["timestamp"])
        if time is None:
            raise Failure(f"line {number}: timestamp: not a date with an offset")
        timeline.append((time, number, "stop" if stop else "start" if "turnOrigin" in record else kind))
    turns = any(kind == "start" for _, _, kind in timeline)
    if not turns and any(record.get("type") in ("user", "assistant") for record in records):
        # A later harness may drop the key: no figure is better than zero minutes.
        raise Failure("turnOrigin: no user or assistant record starts a turn")
    return sorted(timeline)


def coordinator(timeline: list[tuple[int, int, str]], start: int, until: int) -> dict:
    """The coordinator's minutes in the window from `start` to `until`, both in milliseconds.

    A turn starts at a "start" event. It ends at its first stop record; failing that, at its last
    assistant event; failing that, at its start. An assistant event counts, as model time, the
    interval from the event just before it to itself, cut to its turn and to the window.
    """
    turns = [{"spans": []}]  # The first holds what comes before any turn, and is left out.
    previous = None
    for time, _, kind in timeline:
        if kind == "stop":
            turns[-1].setdefault("stop", time)
            continue
        if kind == "start":
            turns.append({"start": time, "last": time, "spans": []})
        elif kind == "assistant":
            turns[-1]["last"] = time
            turns[-1]["spans"].append((previous, time))
        previous = time
    whole, model = [], []
    for turn in turns[1:]:
        end = min(turn.get("stop", turn["last"]), until)
        whole.append((max(turn["start"], start), end))
        model += [(max(begin, start), min(finish, end)) for begin, finish in turn["spans"]]
    return {
        "window_minutes": minutes(until - start),
        "model_minutes": minutes(union(model)),
        "turn_minutes": minutes(union(whole)),
    }


def parsed(name: str, parse):
    """What `parse` makes of the bytes of the file `name`. A failure names the file."""
    try:
        return parse(Path(name).read_bytes())
    except OSError:
        raise Failure(f"{name}: cannot be read") from None
    except Failure as failure:
        raise Failure(f"{name}: {failure}") from None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="minutes.py", description="Read the minutes of workflow runs and of the coordinator."
    )
    parser.add_argument("records", nargs="+", metavar="RECORD.json", help="a run record")
    parser.add_argument("--transcript", metavar="MAIN.jsonl", help="the transcript of the main session")
    parser.add_argument("--until", metavar="ISO8601", help="the end of the window, with an offset or Z")
    arguments = parser.parse_args()
    until = instant(arguments.until)
    if (arguments.transcript is None) != (arguments.until is None):
        parser.error("--transcript and --until go together")
    if arguments.until is not None and until is None:
        parser.error("--until is a date and a time with an offset or Z")
    try:
        runs = [parsed(name, run_of) for name in arguments.records]
        result = report(runs) | {"coordinator": None}
        if until is not None:
            start = min(run["start"] for run in runs)
            if until < start:
                raise Failure("--until: before the start of the first run")
            result["coordinator"] = parsed(
                arguments.transcript,
                lambda data: coordinator(timeline_of(records_of(data)), start, until),
            )
    except Failure as failure:
        print(f"minutes.py: {failure}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
