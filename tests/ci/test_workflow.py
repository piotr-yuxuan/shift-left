"""The workflow file of the pipeline, read as text.

The standard library reads no YAML, so each test reads the lines of the file. The
expectations are what the pipeline must not lose without a test failing: code of others named
by its commit, Ruff at a written version, a token that can only read outside the job that
releases, and a job `release` that runs only after a `gate` that passed, only for a push to
`main` of a repository that is no fork, one at a time, and that names no environment; and a
deadline for each job.
"""

import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def under(lines: list[str], key: str) -> list[str]:
    """The lines of the block that the one line `key:` opens, each without its indent."""
    (start,) = [number for number, line in enumerate(lines) if line.strip() == f"{key}:"]
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line.strip())
    return [line for line in block if line and not line.startswith("#")]


def values(lines: list[str], key: str) -> list[str]:
    """The value of each line `key: value`, the line of a step that starts with a dash included."""
    return [
        line.strip().removeprefix("- ").removeprefix(f"{key}: ")
        for line in lines
        if line.strip().removeprefix("- ").startswith(f"{key}: ")
    ]


class Workflow(unittest.TestCase):
    def setUp(self):
        self.lines = WORKFLOW.read_text().splitlines()
        jobs = self.lines.index("jobs:")
        self.top = self.lines[:jobs]
        # A job is a line with an indent of two spaces, and what follows it up to the next job.
        starts = [n for n, line in enumerate(self.lines) if re.fullmatch(r"  [\w-]+:", line)]
        self.jobs = {
            self.lines[start].strip(" :"): self.lines[start:end]
            for start, end in zip(starts, [*starts[1:], len(self.lines)], strict=True)
            if start > jobs
        }

    def test_the_jobs_are_gate_and_release(self):
        self.assertEqual(list(self.jobs), ["gate", "release"])

    def test_the_pipeline_starts_at_a_push_to_any_branch_and_at_a_pull_request(self):
        self.assertEqual(under(self.top, "on"), ["push:", 'branches: ["**"]', "pull_request:"])

    def test_every_action_is_one_of_github_named_by_a_full_commit_hash(self):
        actions = values(self.lines, "uses")
        self.assertEqual(len(actions), 4)
        for action in actions:
            with self.subTest(action=action):
                self.assertRegex(action, r"^actions/[a-z-]+@[0-9a-f]{40} # v[0-9]+\.[0-9]+\.[0-9]+$")

    def test_ruff_is_installed_once_at_a_full_version(self):
        text = "\n".join(self.lines)
        self.assertEqual(text.count("ruff"), 1)
        self.assertRegex(text, r"ruff==[0-9]+\.[0-9]+\.[0-9]+(\s|$)")

    def test_the_token_can_only_read_outside_the_job_release(self):
        text = "\n".join(self.lines)
        self.assertEqual(text.count("permissions"), 2)
        self.assertNotIn("write-all", text)
        self.assertEqual(under(self.top, "permissions"), ["contents: read"])
        granted = under(self.jobs["release"], "permissions")
        self.assertEqual(sorted(granted), ["contents: write", "deployments: write"])

    def test_release_runs_after_gate_for_a_push_to_main_of_a_repository_that_is_no_fork(self):
        release = self.jobs["release"]
        self.assertEqual(values(release, "needs"), ["gate"])
        (condition,) = values(release, "if")
        # These three terms and no other. One more could be the name of the repository, which
        # has changed once already, or a status function such as `always()`, with which the job
        # no longer waits for a gate that passed.
        terms = {
            "github.event_name == 'push'",
            "github.ref == 'refs/heads/main'",
            "!github.event.repository.fork",
        }
        self.assertEqual(set(condition.split(" && ")), terms)

    def test_a_step_that_fails_fails_its_job(self):
        # With this key on the step of the gate, `release` would run after a gate that failed.
        self.assertNotIn("continue-on-error", "\n".join(self.lines))

    def test_release_names_no_environment(self):
        self.assertNotIn("environment", "\n".join(self.jobs["release"]))

    def test_one_release_runs_at_a_time_and_is_never_cancelled(self):
        concurrency = under(self.jobs["release"], "concurrency")
        self.assertEqual(len(concurrency), 2)
        self.assertRegex(concurrency[0], r"^group: \S+$")
        self.assertEqual(concurrency[1], "cancel-in-progress: false")

    def test_each_job_has_a_deadline_of_less_than_an_hour(self):
        # Without one a job may last six hours, and `release` holds its group all that time.
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                (minutes,) = values(job, "timeout-minutes")
                self.assertLess(int(minutes), 60)

    def test_both_jobs_run_on_the_named_image_with_the_whole_history_and_python_3_14(self):
        for name, job in self.jobs.items():
            with self.subTest(job=name):
                self.assertEqual(values(job, "runs-on"), ["ubuntu-24.04"])
                self.assertEqual(values(job, "fetch-depth"), ["0"])
                self.assertEqual(values(job, "python-version"), ['"3.14"'])

    def test_gate_runs_the_gate_script_without_the_cli(self):
        self.assertEqual(values(self.jobs["gate"], "run")[-1], "ci/gate.sh --no-cli")
        # The step is this one line, the last of its job: it has no key of its own, such as
        # a condition, with which the job would pass though the gate failed or did not run.
        last = [line.strip() for line in self.jobs["gate"] if line.strip()][-1]
        self.assertEqual(last, "- run: ci/gate.sh --no-cli")

    def test_release_runs_the_release_script_alone_and_gives_it_the_token(self):
        release = self.jobs["release"]
        self.assertEqual(values(release, "run"), ["python3 ci/release.py"])
        # The step is the last: what follows its line is its own.
        step = release[release.index("      - run: python3 ci/release.py") :]
        self.assertEqual(under(step, "env"), ["GH_TOKEN: ${{ github.token }}"])


if __name__ == "__main__":
    unittest.main()
