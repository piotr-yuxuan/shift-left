"""The minutes script of the `instrument` skill, through its command line and its decisions.

The expectations come from the definitions that the skill states, computed by hand: the wall
minutes of a stage are the union of the intervals of its finished agents; agents that did not
finish are reported apart; the coordinator has model minutes and turn minutes, cut to a window.
A fixture holds only the keys that the script reads, and times in minutes after T0.

The tests need `python3` on PATH.
"""

import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins" / "shift-left" / "skills" / "instrument"
SCRIPT = SKILL / "minutes.py"
START = datetime(2030, 3, 18, tzinfo=timezone.utc)
T0 = 1_900_022_400_000  # START, in milliseconds since the epoch

# Stands for private text: no stream of the script may show it.
MARKER = "PRIVATE-MARKER"

# Time zones in the POSIX form of TZ, which needs no zone database: UTC, five and a half hours
# east of it, eight hours west of it.
ZONES = ("UTC0", "IST-5:30", "PST8")


def loaded(script: Path):
    """The script as a module, for its decision functions."""
    spec = importlib.util.spec_from_file_location(script.stem, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


minutes = loaded(SCRIPT)


def at(minute: float) -> int:
    """The milliseconds since the epoch, `minute` minutes after T0."""
    return T0 + round(minute * 60000)


def clock(minute: float, offset: timedelta = timedelta(0)) -> str:
    """The same instant as a transcript writes it, or with another offset from UTC."""
    moment = (START + timedelta(minutes=minute)).astimezone(timezone(offset))
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def phase(title: str) -> dict:
    return {"type": "workflow_phase", "title": title}


def agent(title: str, start: float, length: float | None = None, state: str = "progress") -> dict:
    """An agent of a phase: done after `length` minutes, or not finished when there is no length."""
    entry = {"type": "workflow_agent", "phaseTitle": title, "startedAt": at(start), "state": state}
    if length is not None:
        entry |= {"state": "done", "durationMs": round(length * 60000)}
    return entry


def record(run_id: str, start: float, length: float, *progress: dict, status="completed") -> dict:
    """A run record that starts `start` minutes after T0 and lasts `length` minutes."""
    return {
        "runId": run_id,
        "status": status,
        "startTime": at(start),
        "durationMs": round(length * 60000),
        "workflowProgress": list(progress),
    }


def user(minute: float, **keys) -> dict:
    return {"type": "user", "timestamp": clock(minute)} | keys


def turn(minute: float, origin: str = "human") -> dict:
    """The user record that starts a turn."""
    return user(minute, turnOrigin=origin)


def assistant(minute: float, **keys) -> dict:
    return {"type": "assistant", "timestamp": clock(minute)} | keys


def stop(minute: float) -> dict:
    return {"type": "system", "subtype": "stop_hook_summary", "timestamp": clock(minute)}


def stage_figures(*records: dict) -> dict:
    """The report of run records, without the command line."""
    return minutes.report([minutes.run_of(json.dumps(one).encode()) for one in records])


def stages(*records: dict) -> dict:
    """For each stage in order: agents, wall and agent minutes, unfinished agents and their minutes."""
    keys = ("agents", "wall_minutes", "agent_minutes", "unfinished", "unfinished_minutes")
    return {row["stage"]: tuple(row[key] for key in keys) for row in stage_figures(*records)["stages"]}


def coordinator_figures(records: list[dict], start: float = 0, until: float = 60) -> tuple:
    """The model minutes and the turn minutes of transcript records, without the command line."""
    figures = minutes.coordinator(minutes.timeline_of(records), at(start), at(until))
    return figures["model_minutes"], figures["turn_minutes"]


# A main transcript, in order of time. Run records start at T0 and the window ends 90 minutes later.
# Turn 1 starts before the window and has a stop record: 4.5 minutes of it are in the window, and
# 3 of model time. Turn 2 has no stop record and ends at its last assistant event: 15 minutes, and
# 1 + 2 of model time around a wait of 12 minutes for a tool. Turn 3 has neither a stop record nor
# an assistant event. Turn 4 runs past the window: 38 minutes of it are in the window, and 4 + 10
# of model time around a wait of 24 minutes.
TRANSCRIPT = [
    {"type": "summary", "message": {"content": MARKER}},
    turn(-4),
    assistant(-2),
    assistant(3),
    stop(4.5),
    {"type": "attachment", "timestamp": clock(5)},
    turn(20, "task_notification"),
    assistant(21),
    user(33),
    assistant(35),
    assistant(40, isSidechain=True),
    {"type": "system", "subtype": "api_error", "timestamp": clock(41)},
    user(45),
    turn(50),
    turn(52),
    {"type": "queue-operation", "timestamp": clock(53)},
    assistant(56),
    user(80),
    assistant(95),
    stop(97),
    {"type": "mode"},
]
COORDINATOR = {"window_minutes": 90, "model_minutes": 20, "turn_minutes": 57.5}


class Intervals(unittest.TestCase):
    def test_the_union_counts_each_instant_once(self):
        cases = [
            ("nothing", [], 0),
            ("one interval", [(3, 10)], 7),
            ("two that overlap and one apart", [(0, 10), (5, 20), (40, 50)], 30),
            ("one inside another", [(0, 30), (10, 15)], 30),
            ("two that touch", [(0, 10), (10, 20)], 20),
            ("the same twice", [(4, 9), (4, 9)], 5),
            ("not in order", [(40, 50), (5, 20), (0, 10)], 30),
            ("one that ends before it starts", [(0, 10), (30, 20)], 10),
            ("a long one then short ones inside and after", [(0, 100), (10, 20), (90, 120)], 120),
        ]
        for label, intervals, expected in cases:
            with self.subTest(label):
                self.assertEqual(minutes.union(intervals), expected)

    def test_minutes_have_one_decimal(self):
        self.assertEqual(minutes.minutes(400_000), 6.7)
        self.assertEqual(minutes.minutes(1_710_000), 28.5)
        self.assertEqual(minutes.minutes(0), 0)

    def test_minutes_are_rounded_as_round_does_and_not_half_up(self):
        # round(ms / 60000, 1): 0.15 minute is a float just below it, and 0.25 is a tie.
        self.assertEqual(minutes.minutes(9000), 0.1)
        self.assertEqual(minutes.minutes(15000), 0.2)

    def test_an_instant_needs_an_offset(self):
        self.assertEqual(minutes.instant("2030-03-18T00:00:00Z"), T0)
        self.assertEqual(minutes.instant("2030-03-18T00:00:00.250Z"), T0 + 250)
        self.assertEqual(minutes.instant("2030-03-18T05:30:00+05:30"), T0)
        self.assertEqual(minutes.instant("2030-03-17T16:00:00-08:00"), T0)
        for text in ("2030-03-18T00:00:00", "2030-03-18", "yesterday", "", None, 1_900_022_400):
            with self.subTest(text=text):
                self.assertIsNone(minutes.instant(text))


class Stages(unittest.TestCase):
    """The figures of the stages, from run records as plain values."""

    def test_wall_minutes_are_the_union_and_agent_minutes_the_sum(self):
        one = record(
            "wf-a",
            0,
            60,
            phase("Build"),
            agent("Build", 0, 12),
            agent("Build", 8, 12),
            agent("Build", 50, 5),
        )
        # Neither the span, 55, nor the sum, 29, nor the longest, 12.
        self.assertEqual(stages(one), {"Build": (3, 25, 29, 0, 0)})

    def test_an_agent_inside_another_adds_no_wall_minute(self):
        one = record("wf-a", 0, 60, phase("Build"), agent("Build", 0, 30), agent("Build", 10, 5))
        self.assertEqual(stages(one), {"Build": (2, 30, 35, 0, 0)})

    def test_the_total_is_the_union_over_every_finished_agent_and_not_the_sum_of_the_stages(self):
        one = record(
            "wf-a", 0, 60, agent("Build", 0, 20), agent("Check", 10, 30), agent("Check", 50, 4)
        )
        self.assertEqual(stages(one), {"Build": (1, 20, 20, 0, 0), "Check": (2, 34, 34, 0, 0)})
        self.assertEqual(stage_figures(one)["total"], {"wall_minutes": 44, "agent_minutes": 54})

    def test_figures_are_added_in_milliseconds_and_rounded_once(self):
        # Three agents of 20 seconds, one after the other: one minute, where 0.3 three times is 0.9.
        short = record("wf-a", 0, 1, *(agent("Probe", n / 3, 1 / 3) for n in range(3)))
        self.assertEqual(stages(short), {"Probe": (3, 1, 1, 0, 0)})
        self.assertEqual(stage_figures(short)["total"], {"wall_minutes": 1, "agent_minutes": 1})
        # Four agents of 100 seconds: 6.7 minutes, where 1.7 four times is 6.8.
        long = record("wf-b", 0, 400 / 60, *(agent("Scan", n * 100 / 60, 100 / 60) for n in range(4)))
        self.assertEqual(stages(long), {"Scan": (4, 6.7, 6.7, 0, 0)})
        self.assertEqual(stage_figures(long)["total"], {"wall_minutes": 6.7, "agent_minutes": 6.7})
        self.assertEqual(stage_figures(long)["runs"][0]["minutes"], 6.7)

    def test_agents_that_did_not_finish_are_counted_apart_until_the_end_of_their_run(self):
        one = record(
            "wf-a",
            0,
            60,
            agent("Build", 0, 10),
            agent("Build", 30),
            agent("Check", 50),
            agent("Check", 58.5, state="error"),
            status="killed",
        )
        # The run ends at 60: 30 minutes for the one, 10 and 1.5 for the two others.
        self.assertEqual(stages(one), {"Build": (1, 10, 10, 1, 30), "Check": (0, 0, 0, 2, 11.5)})
        self.assertEqual(stage_figures(one)["total"], {"wall_minutes": 10, "agent_minutes": 10})

    def test_an_agent_is_finished_by_its_state_and_not_by_the_keys_that_it_has(self):
        one = record("wf-a", 0, 10, agent("Build", 0, 1) | {"state": "error"})
        self.assertEqual(stages(one), {"Build": (0, 0, 0, 1, 10)})

    def test_the_end_of_an_unfinished_agent_is_the_end_of_its_own_run(self):
        early = record("wf-a", 0, 20, agent("Build", 5), status="killed")
        late = record("wf-b", 30, 60, agent("Build", 40), agent("Build", 45, 5), status="killed")
        # 20 - 5 in the first run, and 90 - 40 in the second.
        self.assertEqual(stages(late, early), {"Build": (1, 5, 5, 2, 65)})

    def test_a_phase_with_no_agent_is_listed_with_zeros_after_the_others(self):
        one = record("wf-a", 0, 60, phase("Ship"), phase("Build"), phase("Lint"), agent("Build", 0, 10))
        self.assertEqual(
            list(stages(one).items()),
            [("Build", (1, 10, 10, 0, 0)), ("Ship", (0,) * 5), ("Lint", (0,) * 5)],
        )

    def test_phases_with_no_agent_are_in_the_order_of_their_first_declaration_over_the_runs(self):
        first = record("wf-a", 0, 10, phase("Ship"), phase("Lint"))
        second = record("wf-b", 5, 10, phase("Lint"), phase("Audit"), phase("Ship"))
        self.assertEqual(list(stages(second, first)), ["Ship", "Lint", "Audit"])
        self.assertEqual(list(stages(first, second)), ["Ship", "Lint", "Audit"])

    def test_stages_are_in_the_order_of_the_earliest_start_of_any_of_their_agents(self):
        one = record(
            "wf-a",
            0,
            60,
            phase("Late"),
            phase("Never"),
            phase("Early"),
            phase("Open"),
            agent("Late", 30, 5),
            agent("Early", 10, 5),
            agent("Late", 20, 5),
            agent("Open", 4),
        )
        self.assertEqual(list(stages(one)), ["Open", "Early", "Late", "Never"])

    def test_run_records_are_merged_by_phase_title(self):
        first = record("wf-a", 0, 30, phase("Review"), agent("Review", 0, 20))
        second = record(
            "wf-b", 5, 30, phase("Fix"), phase("Review"), agent("Review", 10, 20), agent("Fix", 32, 3)
        )
        # One stage, and one union over the two runs: 30 minutes, not 20 + 20.
        expected = {"Review": (2, 30, 40, 0, 0), "Fix": (1, 3, 3, 0, 0)}
        self.assertEqual(stages(second, first), expected)
        self.assertEqual(
            stage_figures(second, first)["total"], {"wall_minutes": 33, "agent_minutes": 43}
        )

    def test_an_agent_of_a_phase_that_was_not_declared_makes_a_stage(self):
        one = record("wf-a", 0, 30, phase("Review"), agent("Elsewhere", 3, 4))
        self.assertEqual(stages(one), {"Elsewhere": (1, 4, 4, 0, 0), "Review": (0,) * 5})

    def test_an_entry_of_another_type_is_not_read(self):
        one = record(
            "wf-a", 0, 30, {"type": "workflow_log", "startedAt": MARKER}, agent("Review", 0, 5)
        )
        self.assertEqual(stages(one), {"Review": (1, 5, 5, 0, 0)})

    def test_runs_are_in_order_of_start_with_their_status_their_start_in_utc_and_their_minutes(self):
        late = record("wf-late", 75.5, 12.5)
        late["startTime"] += 999  # The start is given to the second, with no fraction.
        early = record("wf-early", -30, 100 / 60, status="killed")
        expected = [
            {
                "run_id": "wf-early",
                "status": "killed",
                "started_at": "2030-03-17T23:30:00Z",
                "minutes": 1.7,
            },
            {
                "run_id": "wf-late",
                "status": "completed",
                "started_at": "2030-03-18T01:15:30Z",
                "minutes": 12.5,
            },
        ]
        self.assertEqual(stage_figures(late, early)["runs"], expected)
        self.assertEqual(stage_figures(early, late)["runs"], expected)

    def test_the_same_run_given_twice_is_a_failure(self):
        with self.assertRaises(minutes.Failure):
            stage_figures(record("wf-a", 0, 10), record("wf-b", 0, 10), record("wf-a", 5, 10))


class Coordinator(unittest.TestCase):
    """The figures of the coordinator, from transcript records as plain values."""

    def test_model_minutes_end_at_assistant_events_only(self):
        records = [turn(0), assistant(3), user(13), assistant(14), stop(15)]
        # A wait of ten minutes ends at the user event: it is turn time and not model time.
        self.assertEqual(coordinator_figures(records), (4, 15))

    def test_an_interval_starts_at_the_event_just_before_whatever_its_type(self):
        records = [
            turn(0),
            user(2),
            assistant(3),
            assistant(7),
            user(8),
            user(10),
            assistant(10.5),
            stop(11),
        ]
        self.assertEqual(coordinator_figures(records), (5.5, 11))

    def test_a_turn_with_no_stop_record_ends_at_its_last_assistant_event(self):
        records = [turn(0), assistant(2), user(9), turn(20), assistant(21), stop(22)]
        # The first turn ends at 2 and not at 9, the last event before the next start.
        self.assertEqual(coordinator_figures(records), (3, 4))

    def test_a_turn_with_neither_a_stop_record_nor_an_assistant_event_ends_at_its_start(self):
        records = [turn(0), user(3), turn(5), assistant(6), stop(7)]
        self.assertEqual(coordinator_figures(records), (1, 2))

    def test_the_last_turn_may_be_open(self):
        self.assertEqual(
            coordinator_figures([turn(0), assistant(2), user(3), assistant(8), user(30)]), (7, 8)
        )
        self.assertEqual(coordinator_figures([turn(0), assistant(2), turn(10)]), (2, 2))

    def test_a_turn_ends_at_its_first_stop_record(self):
        records = [
            turn(0),
            assistant(1),
            stop(2),
            stop(30),
            turn(40),
            assistant(41),
            stop(42),
            stop(43),
        ]
        self.assertEqual(coordinator_figures(records), (2, 4))

    def test_a_stop_record_after_the_next_start_ends_the_next_turn(self):
        records = [turn(0), assistant(1), turn(10), assistant(12), stop(13)]
        self.assertEqual(coordinator_figures(records), (3, 4))

    def test_an_assistant_event_after_the_stop_record_is_cut_to_its_turn(self):
        records = [turn(0), assistant(2), stop(3), assistant(8), turn(10), stop(11)]
        # Of the interval from 2 to 8, the minute before the stop record is in the turn.
        self.assertEqual(coordinator_figures(records), (3, 4))

    def test_an_assistant_event_before_the_first_turn_counts_in_neither_figure(self):
        records = [user(0), assistant(2), turn(5), assistant(6), stop(7)]
        self.assertEqual(coordinator_figures(records), (1, 2))

    def test_both_figures_are_cut_to_the_window(self):
        before = [turn(-5), assistant(-1), assistant(3), stop(4)]
        after = [turn(50), assistant(58), assistant(65), stop(70)]
        outside = [turn(-20), assistant(-15), stop(-14), turn(80), assistant(85), stop(86)]
        self.assertEqual(coordinator_figures(before), (3, 4))
        self.assertEqual(coordinator_figures(after), (10, 10))
        self.assertEqual(coordinator_figures(outside), (0, 0))
        self.assertEqual(coordinator_figures(before + after + outside), (13, 14))
        self.assertEqual(coordinator_figures(before + after, start=-10, until=100), (23, 29))

    def test_records_are_read_in_order_of_time_and_not_of_line(self):
        records = [turn(0), assistant(3), user(13), assistant(14), stop(15), turn(20), assistant(22)]
        for seed in range(5):
            with self.subTest(seed=seed):
                shuffled = records[:]
                random.Random(seed).shuffle(shuffled)
                self.assertEqual(coordinator_figures(shuffled), (6, 17))

    def test_records_of_the_same_time_keep_the_order_of_their_lines(self):
        # The stop record is on the line before the start of the next turn: it ends the first turn.
        self.assertEqual(coordinator_figures([turn(0), assistant(2), stop(10), turn(10)]), (2, 10))
        # On the line after, it ends the turn that has just started, and the first ends at 2.
        self.assertEqual(coordinator_figures([turn(0), assistant(2), turn(10), stop(10)]), (2, 2))

    def test_only_user_and_assistant_records_with_a_timestamp_and_off_the_sidechain_are_events(self):
        records = [
            {"type": "last-prompt"},
            turn(0),
            {"type": "attachment", "timestamp": clock(1)},
            {"type": "queue-operation", "timestamp": clock(2)},
            {"type": "system", "subtype": "api_error", "timestamp": clock(3)},
            assistant(4, isSidechain=True),
            user(5, isSidechain=True, turnOrigin="human"),
            {"type": "assistant"},
            {"type": "user", "turnOrigin": "human"},
            {"timestamp": clock(6)},
            {"type": "system", "timestamp": clock(7)},
            {"type": "system", "subtype": "stop_hook_summary"},
            assistant(9, isSidechain=False),
            user(15),
        ]
        expected = [(at(0), 2, "start"), (at(9), 13, "assistant"), (at(15), 14, "user")]
        self.assertEqual(minutes.timeline_of(records), expected)
        self.assertEqual(coordinator_figures(records), (9, 9))

    def test_the_timeline_is_in_order_of_time_with_the_line_of_each_record(self):
        records = [stop(8), assistant(5), turn(1), user(5), turn(5, "peer")]
        expected = [
            (at(1), 3, "start"),
            (at(5), 2, "assistant"),
            (at(5), 4, "user"),
            (at(5), 5, "start"),
            (at(8), 1, "stop"),
        ]
        self.assertEqual(minutes.timeline_of(records), expected)

    def test_timestamps_with_another_offset_are_the_same_instants(self):
        india = timedelta(hours=5, minutes=30)
        records = [
            {"type": "user", "timestamp": clock(0, india), "turnOrigin": "human"},
            {"type": "assistant", "timestamp": clock(3, timedelta(hours=-8))},
            {"type": "system", "subtype": "stop_hook_summary", "timestamp": clock(4, india)},
        ]
        self.assertEqual(coordinator_figures(records), (3, 4))

    def test_a_timestamp_that_is_not_a_date_with_an_offset_is_a_failure(self):
        for timestamp in (MARKER, "2030-03-18T00:03:00", 1_900_022_400, None, ""):
            for broken in (assistant(3), turn(3), user(3), stop(3)):
                with self.subTest(timestamp=timestamp, type=broken["type"]):
                    records = [turn(0), broken | {"timestamp": timestamp}]
                    with self.assertRaises(minutes.Failure) as failure:
                        minutes.timeline_of(records)
                    self.assertIn("line 2", str(failure.exception))
                    self.assertNotIn(MARKER, str(failure.exception))

    def test_a_turn_starts_at_the_key_whatever_its_value(self):
        for value in (None, ""):
            with self.subTest(value=value):
                records = [user(0, turnOrigin=value), assistant(3)]
                self.assertEqual(coordinator_figures(records), (3, 3))

    def test_events_with_no_turn_marker_at_all_are_a_failure(self):
        for records in ([user(0), assistant(1)], [assistant(1), stop(2)], [user(0)]):
            with self.subTest(records=len(records)), self.assertRaises(minutes.Failure) as failure:
                coordinator_figures(records)
            self.assertIn("turnOrigin", str(failure.exception))

    def test_a_transcript_with_no_event_has_no_coordinator_minute(self):
        records = [{"type": "attachment", "timestamp": clock(1)}, stop(2), {"type": "mode"}]
        self.assertEqual(coordinator_figures(records), (0, 0))
        self.assertEqual(coordinator_figures([]), (0, 0))

    def test_the_window_is_reported_in_minutes(self):
        figures = minutes.coordinator(minutes.timeline_of(TRANSCRIPT), at(0), at(90))
        self.assertEqual(figures, COORDINATOR)
        figures = minutes.coordinator(minutes.timeline_of(TRANSCRIPT), at(-10), at(100.5))
        self.assertEqual(figures, {"window_minutes": 110.5, "model_minutes": 29, "turn_minutes": 68.5})


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        home = self.scratch / "home"
        home.mkdir()
        self.environment = {"PATH": os.environ["PATH"], "HOME": str(home)}

    def written(self, name: str, content) -> str:
        """The path of a scratch file: text as it is, a list as lines of JSON, a record as JSON."""
        if isinstance(content, list):
            content = "".join(json.dumps(line) + "\n" for line in content)
        elif not isinstance(content, str):
            content = json.dumps(content)
        (self.scratch / name).write_text(content, encoding="utf-8")
        return str(self.scratch / name)

    def script(self, *arguments: str, **environment: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            env=self.environment | environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def assertDone(self, result) -> dict:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn(MARKER, result.stdout)
        return json.loads(result.stdout)

    def assertFailed(self, result) -> str:
        """Status 2: nothing on standard output, and one line on standard error, with no value."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertNotIn(MARKER, result.stderr)
        return result.stderr

    def assertWrongCall(self, result) -> None:
        """Status 2 and nothing on standard output; the usage may come before the line."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(MARKER, result.stderr)


class Report(CommandLine):
    def setUp(self):
        super().setUp()
        hidden = {"label": MARKER, "promptPreview": MARKER, "resultPreview": MARKER}
        first = record(
            "wf-a",
            0,
            45,
            phase("Build"),
            phase("Check"),
            phase("Ship"),
            agent("Build", 0, 10) | hidden,
            agent("Build", 5, 20) | hidden,
            agent("Check", 20, 6) | hidden,
            agent("Check", 30) | hidden,
            status="killed",
        )
        first |= {"summary": MARKER, "logs": [MARKER], "result": {"text": MARKER}, "script": MARKER}
        second = record(
            "wf-b",
            10,
            50,
            phase("Check"),
            phase("Build"),
            agent("Check", 40, 10),
            agent("Build", 12, 18),
        )
        self.first = self.written("first.json", first | {"error": MARKER})
        self.second = self.written("second.json", second)
        self.transcript = self.written("main.jsonl", TRANSCRIPT)

    def window(
        self, *records: str, transcript: str | None = None, until: float | str = 90, **zone: str
    ):
        """Run the script on run records, with a transcript and a window that ends at `until`."""
        until = until if isinstance(until, str) else clock(until)
        arguments = [*records, "--transcript", transcript or self.transcript, "--until", until]
        return self.script(*arguments, **zone)

    def test_the_report_of_two_run_records_that_overlap_in_any_order(self):
        zeros = {"wall_minutes": 0, "agent_minutes": 0, "unfinished": 0, "unfinished_minutes": 0}
        build = {"wall_minutes": 30, "agent_minutes": 48, "unfinished": 0, "unfinished_minutes": 0}
        check = {"wall_minutes": 16, "agent_minutes": 16, "unfinished": 1, "unfinished_minutes": 15}
        expected = {
            "runs": [
                {
                    "run_id": "wf-a",
                    "status": "killed",
                    "started_at": "2030-03-18T00:00:00Z",
                    "minutes": 45,
                },
                {
                    "run_id": "wf-b",
                    "status": "completed",
                    "started_at": "2030-03-18T00:10:00Z",
                    "minutes": 50,
                },
            ],
            "stages": [
                {"stage": "Build", "agents": 3} | build,
                {"stage": "Check", "agents": 2} | check,
                {"stage": "Ship", "agents": 0} | zeros,
            ],
            "total": {"wall_minutes": 40, "agent_minutes": 64},
            "coordinator": None,
        }
        self.assertEqual(self.assertDone(self.script(self.second, self.first)), expected)
        self.assertEqual(self.assertDone(self.script(self.first, self.second)), expected)

    def test_the_report_is_one_json_object_with_its_keys_in_the_stated_order(self):
        result = self.script(self.first)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        report = self.assertDone(result)
        self.assertEqual(list(report), ["runs", "stages", "total", "coordinator"])
        self.assertEqual(list(report["runs"][0]), ["run_id", "status", "started_at", "minutes"])
        keys = ["stage", "agents", "wall_minutes", "agent_minutes", "unfinished", "unfinished_minutes"]
        self.assertEqual(list(report["stages"][0]), keys)
        self.assertEqual(list(report["total"]), ["wall_minutes", "agent_minutes"])

    def test_the_window_runs_from_the_earliest_start_of_the_runs_to_until(self):
        report = self.assertDone(self.window(self.second, self.first))
        self.assertEqual(report["coordinator"], COORDINATOR)
        self.assertEqual(
            list(report["coordinator"]), ["window_minutes", "model_minutes", "turn_minutes"]
        )
        # The second run starts at 10: the window loses the 3 and the 4.5 minutes of the first turn.
        expected = {"window_minutes": 80, "model_minutes": 17, "turn_minutes": 53}
        self.assertEqual(self.assertDone(self.window(self.second))["coordinator"], expected)

    def test_the_order_of_the_lines_the_zone_and_a_line_being_written_do_not_change_the_report(self):
        expected = self.assertDone(self.window(self.first))
        self.assertEqual(expected["coordinator"], COORDINATOR)
        self.assertEqual(expected["runs"][0]["started_at"], "2030-03-18T00:00:00Z")
        shuffled = TRANSCRIPT[:]
        random.Random(7).shuffle(shuffled)
        lines = "".join(json.dumps(line) + "\n" for line in shuffled)
        transcripts = {
            "shuffled": self.written("shuffled.jsonl", lines),
            "a last line being written": self.written("live.jsonl", lines + '{"type": "assi'),
            "an open last turn": self.written(
                "open.jsonl", [line for line in TRANSCRIPT if line != stop(97)]
            ),
        }
        untils = [clock(90), clock(90, timedelta(hours=5, minutes=30)), clock(90, timedelta(hours=-8))]
        for label, transcript in transcripts.items():
            for until in untils:
                for zone in ZONES:
                    with self.subTest(transcript=label, until=until, zone=zone):
                        result = self.window(self.first, transcript=transcript, until=until, TZ=zone)
                        self.assertEqual(self.assertDone(result), expected)

    def test_a_window_may_end_at_the_start_of_the_first_run_and_not_before(self):
        report = self.assertDone(self.window(self.first, self.second, until=0))
        expected = {"window_minutes": 0, "model_minutes": 0, "turn_minutes": 0}
        self.assertEqual(report["coordinator"], expected)
        self.assertFailed(self.window(self.first, self.second, until=-0.5))
        self.assertFailed(self.window(self.second, until=9))

    def test_a_valid_call_prints_no_private_text(self):
        result = self.window(self.first, self.second)
        self.assertDone(result)
        self.assertNotIn(MARKER, result.stdout + result.stderr)

    def test_a_run_record_of_the_wrong_shape_is_a_failure_that_names_the_path_of_the_key(self):
        def without(key):
            return lambda one: one.pop(key)

        def entry(index, change):
            return lambda one: change(one["workflowProgress"][index])

        def having(**keys):
            return lambda one: one.update(keys)

        cases = [
            ("no progress", without("workflowProgress"), "workflowProgress"),
            ("no run id", without("runId"), "runId"),
            ("no status", without("status"), "status"),
            ("no start", without("startTime"), "startTime"),
            ("no duration", without("durationMs"), "durationMs"),
            ("a start that is text", having(startTime=MARKER), "startTime"),
            ("a start that no date holds", having(startTime=10**30), "startTime"),
            ("a duration that is true", having(durationMs=True), "durationMs"),
            ("a status that is a number", having(status=3), "status"),
            ("progress that is an object", having(workflowProgress={}), "workflowProgress"),
            (
                "an entry that is text",
                lambda one: one["workflowProgress"].append(MARKER),
                "workflowProgress[3]",
            ),
            ("an entry with no type", entry(1, without("type")), "workflowProgress[1].type"),
            ("a phase with no title", entry(0, without("title")), "workflowProgress[0].title"),
            (
                "an agent with no phase",
                entry(1, without("phaseTitle")),
                "workflowProgress[1].phaseTitle",
            ),
            ("an agent with no state", entry(1, without("state")), "workflowProgress[1].state"),
            ("an agent with no start", entry(2, without("startedAt")), "workflowProgress[2].startedAt"),
            (
                "a start that is text",
                entry(2, having(startedAt=MARKER)),
                "workflowProgress[2].startedAt",
            ),
            (
                "done with no duration",
                entry(1, without("durationMs")),
                "workflowProgress[1].durationMs",
            ),
            (
                "a duration that is true",
                entry(1, having(durationMs=True)),
                "workflowProgress[1].durationMs",
            ),
            (
                "a duration not whole",
                entry(1, having(durationMs=1.5)),
                "workflowProgress[1].durationMs",
            ),
        ]
        for label, change, path in cases:
            with self.subTest(label, path=path):
                one = record("wf-a", 0, 60, phase("Build"), agent("Build", 0, 10), agent("Build", 20))
                change(one)
                line = self.assertFailed(self.script(self.written("wrong.json", one)))
                self.assertIn(f"wrong.json: {path}: ", line)

    def test_a_file_that_is_not_a_run_record_is_a_failure(self):
        contents = {
            "text": "not json " + MARKER,
            "nothing": "",
            "a list": "[]",
            "a number that is not json": '{"runId": "wf-a", "status": "completed", "startTime": NaN}',
        }
        for label, content in contents.items():
            with self.subTest(label):
                line = self.assertFailed(self.script(self.written("wrong.json", content)))
                self.assertIn("wrong.json: ", line)
        self.assertIn(
            "missing.json: ", self.assertFailed(self.script(str(self.scratch / "missing.json")))
        )
        self.assertFailed(self.script(self.first, str(self.scratch / "missing.json")))

    def test_the_same_run_given_twice_is_a_failure(self):
        self.assertFailed(self.script(self.first, self.second, self.first))

    def test_a_transcript_of_the_wrong_shape_is_a_failure_that_names_the_file(self):
        lines = [json.dumps(line) for line in TRANSCRIPT]
        cut = '{"type": "assi ' + MARKER
        contents = {
            "a line in the middle that does not parse": "\n".join(lines[:6] + [cut] + lines[6:]) + "\n",
            "a first line that does not parse": "\n".join([cut] + lines) + "\n",
            "an empty line in the middle": "\n".join(lines[:6] + [""] + lines[6:]) + "\n",
            "a line that is not an object": "\n".join(lines + ['"' + MARKER + '"', lines[0]]) + "\n",
            "a timestamp that is not a date": [turn(0), assistant(3) | {"timestamp": MARKER}],
            "a timestamp with no offset": [
                turn(0),
                assistant(3) | {"timestamp": "2030-03-18T00:03:00"},
            ],
            "no turn marker": [
                {k: v for k, v in line.items() if k != "turnOrigin"} for line in TRANSCRIPT
            ],
        }
        for label, content in contents.items():
            with self.subTest(label):
                transcript = self.written("wrong.jsonl", content)
                line = self.assertFailed(self.window(self.first, transcript=transcript))
                self.assertIn("wrong.jsonl: ", line)
        missing = str(self.scratch / "missing.jsonl")
        self.assertIn("missing.jsonl: ", self.assertFailed(self.window(self.first, transcript=missing)))

    def test_only_a_last_line_that_does_not_parse_is_left_out(self):
        lines = "".join(json.dumps(line) + "\n" for line in TRANSCRIPT)
        tails = {"cut": '{"type": "assi', "cut and ended": '{"type": "assi\n', "empty": "\n"}
        for label, tail in tails.items():
            with self.subTest(label):
                transcript = self.written("live.jsonl", lines + tail)
                report = self.assertDone(self.window(self.first, transcript=transcript))
                self.assertEqual(report["coordinator"], COORDINATOR)

    def test_a_line_is_a_line_of_the_file_whatever_characters_its_text_holds(self):
        # A line separator of Unicode inside a text is not the end of a record.
        text = {"message": {"content": "one\u2028two\u2029three\u0085four"}}
        lines = "".join(json.dumps(line | text, ensure_ascii=False) + "\n" for line in TRANSCRIPT)
        self.assertIn("\u2028", lines)
        report = self.assertDone(self.window(self.first, transcript=self.written("wide.jsonl", lines)))
        self.assertEqual(report["coordinator"], COORDINATOR)

    def test_a_wrong_call_prints_nothing_on_standard_output(self):
        window = ["--transcript", self.transcript, "--until"]
        calls = [
            [],
            [self.first, "--until", clock(90)],
            [self.first, "--transcript", self.transcript],
            [self.first, *window, "2030-03-18T01:30:00"],
            [self.first, *window, "2030-03-18"],
            [self.first, *window, MARKER],
            [self.first, *window],
            [*window, clock(90)],
            [self.first, "--window", "90"],
        ]
        for call in calls:
            for zone in ZONES:
                with self.subTest(call=call[1:], zone=zone):
                    self.assertWrongCall(self.script(*call, TZ=zone))

    def test_a_copy_of_the_script_runs_alone_from_any_directory_with_an_empty_environment(self):
        copy = self.scratch / "a copy (1)" / "minutes.py"
        copy.parent.mkdir()
        shutil.copy(SCRIPT, copy)
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(copy), self.first],
            env={},
            cwd=self.scratch,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(self.assertDone(result)["total"], {"wall_minutes": 26, "agent_minutes": 36})


if __name__ == "__main__":
    unittest.main()
