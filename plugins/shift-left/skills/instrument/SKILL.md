---
name: instrument
description: Record what the review of a plan found and read what its workflow runs cost. Use when coordinating the review of a plan (to give each reviewer and fixer the schema of its answer, to store their findings in one file per plan, and to summarise them before the handoff), when answering as a reviewer or a fixer under that schema, and when a workflow run has ended and its minutes per stage, or the coordinator's minutes, are to be reported.
---

# Instrument

Two scripts that turn what a plan cost and what its review found into data, so that
both are read from files and not from memory.

- `findings.py` keeps the findings of the reviews of one plan in one JSON file, under
  the schema of `finding.schema.json`.
- `minutes.py` reads the minutes of ended workflow runs, per stage, and the minutes
  of the coordinator.

Loading this skill shows its base directory, written `<base>` below. Run the scripts
from it as shown, with the path in double quotes, since it may hold spaces. They need
`python3`, 3.11 or later, and nothing outside the standard library; they depend on no
variable of the harness and on no working directory. `findings.py` also needs `git`
and a POSIX system.

Both scripts end with one of three statuses.

- 0: done. The result is JSON on standard output.
- 1, `findings.py` only: an answer or the findings file was read and rejected.
  Standard output holds `{"errors": [{"path": ..., "rule": ...}]}` and nothing was
  written. A path looks like `answer.findings[0].line` or `file.findings[2].id`. A
  rule is a keyword of the schema, such as `enum`, or the words of a rule. Correct
  the answer and run the command again.
- 2: the script could not do its job, or the call was wrong. Standard output is
  empty and standard error says why in one line.

Neither script prints the text of a finding or of a transcript: an error names a path
and a rule, never the value that it met. Of a run record, `minutes.py` prints the
identifier, the status and the phase titles as they are, and no other text. Phase
titles come from the script of the workflow, so they must hold no private text.

## Findings

A finding has fourteen fields. `finding.schema.json` is the one authority on them, on
their values and on who writes them; each property carries its definition, the three
severities included. The scripts hold no copy: to change a field, a value or a role,
edit that file. It is written in a small subset of JSON Schema, and a keyword outside
the subset makes every command end with status 2.

| Role | Writes |
|------|--------|
| reviewer | `id`, `file`, `line`, `severity`, `summary`, `failure_scenario`, `fix`, `lens`, `subject`, when the finding is added |
| fixer | `disposition`: `fixed` or `declined`, on a finding that is `open` |
| coordinator | `origin`, `disclosed_before_review`, `carry_over_of`, and any `disposition` |

When a finding is added it also takes the round as `round_found` and `open` as
`disposition`; `origin`, `disclosed_before_review` and `carry_over_of` are null until
the coordinator sets them. The table is a reading aid: `schema --role ROLE` prints
what the schema file holds for a role.

### Where the file lives

One file per plan, `{"findings": [...]}`, at a path that the caller chooses. Keep it
in a directory that git ignores, in a checkout that outlives the worktree of the
plan: removing a worktree deletes its ignored files with it. Findings can quote
private code, so `findings.py` refuses to write a file unless git says that it
ignores it and the temporary file `.<name>.<pid>.tmp` beside it that a write goes
through, and a refused write creates nothing. Any ignore rule counts, a personal one
included; a variable of the caller that names another repository or injects a rule,
such as `GIT_DIR`, is not passed to git. A write replaces the whole file or changes
nothing, and writers wait for each other for up to a minute.

### Who runs what, and when

1. *Before a review round.* Give each reviewer the schema of its answer, its lens,
   and the number of the round. A lens is a lower-case word such as `correctness`. A
   reviewer numbers its findings from 1: the id of the second finding of the lens
   `correctness` in round 1 is `r1-correctness-2`. A reviewer whose own instructions
   use other grades applies the three severities of the schema.

   ```
   python3 "<base>/findings.py" schema --role reviewer
   ```

2. *After each review round:* one `add` for each reviewer, with its answer on
   standard input. An answer with no finding is valid. The command refuses a finding
   of another lens or round, and an id that the file already holds.

   ```
   python3 "<base>/findings.py" add --file FILE --round N --lens L < answer.json
   ```

3. *After each fix round:* one `set` with the answer of the fixer,
   `{"updates": [{"id": ..., "disposition": ...}]}`. Its schema is
   `schema --role fixer`.

   ```
   python3 "<base>/findings.py" set --file FILE --role fixer < answer.json
   ```

4. *Before the handoff:* the coordinator classifies each finding with a `set` of its
   own, whose schema is `schema --role coordinator`, then reads the summary. A
   `carry_over_of` names a finding of an earlier round. `codebook.md`, beside the
   scripts, defines each value of `origin`.

   ```
   python3 "<base>/findings.py" set --file FILE --role coordinator < answer.json
   python3 "<base>/findings.py" summary --file FILE
   ```

The summary counts the findings of each round by severity and all of them by
disposition, and gives `open_serious`: the findings that are blocking or major and
still open.

Every command first checks the whole file, so one that was edited by hand and breaks
the schema or a rule is rejected until it is corrected.

## Minutes

The harness writes the record of a workflow run when the run ends, so a run cannot
report its own minutes: run `minutes.py` afterwards.

```
python3 "<base>/minutes.py" RECORD.json [RECORD.json ...] [--transcript MAIN.jsonl --until ISO8601]
```

### Finding the files

The answer of the workflow tool names the directory that holds the transcripts of the
agents of the run. The run record and the transcript of the main session follow from
it:

```
transcripts="<the directory that the answer of the workflow tool names>"
session="$(dirname "$(dirname "$(dirname "$transcripts")")")"
record="$session/workflows/$(basename "$transcripts").json"
main="$session.jsonl"
```

Give every run record of the plan in one call, in any order: they are merged.

### The figures

A stage is a phase title of the workflow. The run records given are merged by stage,
so agents of two runs under the same title are one stage. An agent is finished when
its state is `done`.

- `wall_minutes` of a stage: the length of the union of the intervals of its finished
  agents, each from its start to its start plus its duration. Two agents that run at
  the same time count once, and a gap between two agents counts for nothing.
- `agent_minutes`: the sum of the durations of its finished agents.
- `unfinished` and `unfinished_minutes`: the agents that did not finish, for example
  because the run was killed, and for each the time from its start to the end of its
  run. They are in neither figure above.
- `total`: the same two figures over every finished agent. Stages overlap, so do not
  add up their wall minutes: read `total.wall_minutes`.
- `runs`: each run with its status, its start in UTC and the minutes of its record.

A phase that was declared and never reached is listed with zeros.

With `--transcript` and `--until`, `coordinator` gives two bounds of the work of the
main session in a window. The window runs from the earliest start of the runs given
to `--until`: pass the moment of the handoff to the owner, as a date and a time with
an offset or `Z`, for example the output of `date -u +%Y-%m-%dT%H:%M:%SZ` at that
moment.

- `model_minutes`: the time that the model of the main session spent producing
  output. For each `assistant` event, the interval from the event just before it to
  itself, cut to its turn and to the window; then the length of their union. A lower
  bound: it leaves out every tool call.
- `turn_minutes`: the length of the union of the turns, cut to the window. An upper
  bound: it includes every wait inside a turn, for a command or for a person.
- `window_minutes`: the length of the window.

An event is a record of type `user` or `assistant` that has a timestamp and is not a
sidechain record; events are read in order of time. A turn starts at an event that
has the key `turnOrigin`: a message from a person, or one from the harness, such as
the notice that a task has ended. It ends at the first `stop_hook_summary` record
before the next turn starts; failing that, at its last `assistant` event; failing
that, at its start.

Report both bounds. Where one figure is needed, use `model_minutes`, and read a large
gap between the two as a sign of waiting.

The transcript of a session that is still open can be read: a last line that is being
written is left out. A transcript that holds `user` or `assistant` records, events or
not, of which none starts a turn is refused, since no figure is better than a wrong
zero.

## Codebook

`codebook.md` defines the labels that a rater gives to a finding once the plan is
done: category, origin, knowable and cheapest preventer. Only origin is a field of a
finding.
