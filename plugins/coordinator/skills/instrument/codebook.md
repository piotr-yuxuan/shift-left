# Codebook

How the findings of a review are labelled once a plan is done, so that two raters give
the same label to the same finding. Only origin is a field of a finding; the three
other labels are given afterwards by a rater, and no field carries them.

A finding is serious when its severity is blocking or major. The severities are
defined in `finding.schema.json`.

## Category

A label given afterwards to a serious finding. It is not a field. Try the categories
in this order and take the first that fits.

1. Requirement missed: the change fails an explicit statement of its plan: a criterion
   unmet, a required part absent, or a change outside the declared scope. The sentence
   of the plan can be quoted.
2. Cannot fail: a test or a check of the change passes whether or not the property it
   claims holds, or a decision of the delivered code has no test that could fail. A
   defect can be named that the check still passes.
3. Environment leak: the result depends on state outside the sandbox of the change, or
   the code changes such state: inherited variables, the real home, the desktop
   session, a resource shared with concurrent sessions, the live tree.
4. Correctness: the delivered code gives a wrong result, drops data silently or
   mishandles a failure path, in a clean environment and within its scope.
5. Other: none of the above, for example a limit of a platform, a seam between two
   tracks, design, a document.

## Origin

A field of a finding, set by the coordinator. Take the first value that fits.

- `plan-or-brief`: the text of the plan or of the brief prescribed the defect. An
  implementation that obeyed it would have the defect, whichever commit carries it.
- `coordinator`: introduced by a commit on the branch of the plan that neither the
  implementer nor a fixer made: a hotfix, the resolution of a merge.
- `fix-round`: introduced by the commits of a fixer, an incomplete fix and a regression
  included.
- `first-iteration`: introduced by the commits of the implementer before the first
  handoff. For something that is missing, the stage that owed it.

## Knowable

A label given afterwards: could the author have known before the handoff? It is
hindsight.

- Yes: the plan, the brief, the change and commands that run in the sandbox of the
  author were enough.
- Partly: it needed a fact about a platform, a tool or a context that the plan did not
  name, and that a probe or a direct question would have given.
- No: not obtainable before the handoff by any reasonable means.

## Cheapest preventer

A label given afterwards. Take the earliest that would have caught the defect.

1. Deterministic check: a script, a hook, a lint rule or a tool that needs no
   judgement.
2. Evidence gate: evidence demanded before the handoff and chosen by someone other
   than the author: the commands of the plan, a scope check, a mutant, a review of
   each fix.
3. Review of the plan: the fault is in the text of the plan or of the brief.
4. Checklist line: no script or gate could catch it; a question put to the author
   would have.
5. Reference knowledge: the author lacked a fact about a platform or a tool that can
   be verified.
