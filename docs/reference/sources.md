# Sources

The works that shift-left's plugins and documentation rely on, with what each takes,
where, and where it departs from the work. A skill or a guide that names its source
stays the authority for its own text; this page gathers them, so that each rule can be
checked against what it came from.

## The project

**Larry Smith, "Shift-Left Testing", 2001.** *Dr. Dobb's Journal*, September 2001,
[drdobbs.com/shiftleft-testing/184404768](https://drdobbs.com/shiftleft-testing/184404768).

- Taken: the name, and the aim of moving quality earlier in the work.
- Where: the repository's name, and the question that
  [About `workflow:plans`](../explanation/workflow-plans.md) opens with.
- Departs: Smith moves testing towards the start of a project; shift-left moves what
  reviews of a coding agent's change find to the moment the code is first written.

## `principles`: the guides of `programming-principles`

Each of the sixteen guides holds a definition, two worked examples and a review question,
written for shift-left, and names the work it rests on, in its section "References".

| Guide | Work |
|---|---|
| [Locality](../../plugins/principles/skills/programming-principles/references/locality.md) | Carson Gross, [Locality of Behaviour](https://htmx.org/essays/locality-of-behaviour/) |
| [Separation of concerns](../../plugins/principles/skills/programming-principles/references/concerns.md) | Edsger W. Dijkstra, [On the role of scientific thought](https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html), EWD 447 |
| [DRY](../../plugins/principles/skills/programming-principles/references/dry.md) | Andrew Hunt and David Thomas, [The Evils of Duplication](https://media.pragprog.com/titles/tpp20/dry.pdf) |
| [Low complexity](../../plugins/principles/skills/programming-principles/references/complexity.md) | Arthur H. Watson and Thomas J. McCabe, [Structured Testing](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication500-235.pdf), NIST Special Publication 500-235; Ruff's rule [C901](https://docs.astral.sh/ruff/rules/complex-structure/) |
| [High cohesion](../../plugins/principles/skills/programming-principles/references/cohesion.md) | Robert C. Martin, [The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html) |
| [Low coupling](../../plugins/principles/skills/programming-principles/references/coupling.md) | David L. Parnas, [On the Criteria To Be Used in Decomposing Systems into Modules](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html) |
| [Single responsibility](../../plugins/principles/skills/programming-principles/references/responsibility.md) | Robert C. Martin, [The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html) |
| [Information hiding](../../plugins/principles/skills/programming-principles/references/information-hiding.md) | David L. Parnas, [On the Criteria To Be Used in Decomposing Systems into Modules](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html) |
| [Useful abstractions](../../plugins/principles/skills/programming-principles/references/abstractions.md) | John Ousterhout, [Managing Complexity](https://web.stanford.edu/~ouster/cgi-bin/cs190-spring15/lecture.php?topic=complexity) |
| [Duplication over the wrong abstraction](../../plugins/principles/skills/programming-principles/references/duplication.md) | Sandi Metz, [The Wrong Abstraction](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction) |
| [YAGNI](../../plugins/principles/skills/programming-principles/references/yagni.md) | Martin Fowler, [YAGNI](https://martinfowler.com/bliki/Yagni.html) |
| [Decisions and effects](../../plugins/principles/skills/programming-principles/references/decisions-and-effects.md) | Gary Bernhardt, [Functional Core, Imperative Shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell) |
| [Explicit invariants](../../plugins/principles/skills/programming-principles/references/invariants.md) | Alexis King, [Parse, don't validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/); Python's [dataclasses](https://docs.python.org/3/library/dataclasses.html) |
| [Resource ownership](../../plugins/principles/skills/programming-principles/references/resources.md) | The C++ Core Guidelines, edited by Bjarne Stroustrup and Herb Sutter, on [resource management](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#S-resource) and on [critical sections](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#Rconc-time); Python's [contextlib](https://docs.python.org/3/library/contextlib.html) |
| [Readability](../../plugins/principles/skills/programming-principles/references/readability.md) | Tim Peters, [The Zen of Python](https://peps.python.org/pep-0020/), PEP 20 |
| [Meaningful verification](../../plugins/principles/skills/programming-principles/references/verification.md) | Erik Kuefler, [Test Behaviors, Not Methods](https://testing.googleblog.com/2014/04/testing-on-toilet-test-behaviors-not.html), and Rich Martin, [Effective Testing](https://testing.googleblog.com/2014/05/testing-on-toilet-effective-testing.html), in Google's Testing on the Toilet |

## `principles`: `karpathy-guidelines`

**Andrej Karpathy, notes on coding with Claude, 2026.** A post on X, 26 January 2026,
[x.com/karpathy/status/2015883857489522876](https://x.com/karpathy/status/2015883857489522876).

- Taken: the pitfalls of coding with a language model that the guidelines below were
  derived from, through them.
- Where: the first line of
  [`SKILL.md`](../../plugins/principles/skills/karpathy-guidelines/SKILL.md) links it.

**Jiayuan Zhang (forrestchang), the Karpathy guidelines, 2026.**
`skills/karpathy-guidelines/SKILL.md` of
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), under
MIT. The repository names forrestchang as its author, the GitHub account whose profile
gives the name Jiayuan Zhang; it now lives under the organisation multica-ai, and its
first address, `github.com/forrestchang/andrej-karpathy-skills`, leads there.

- Taken: the whole file, copied unchanged at commit
  `2c606141936f1eeef17fa3043a72095b4765b9c2`, as
  [`NOTICE.md`](../../plugins/principles/skills/karpathy-guidelines/NOTICE.md) records.
- Where: `plugins/principles/skills/karpathy-guidelines/`; the reviewer agent applies
  its test that every changed line traces to the request, and the shared instructions
  name it.
- Departs: not in the file. Around it, `workflow:plans` counts a move on a concept that
  the user approved with a plan as part of the request, as
  [About `workflow:plans`](../explanation/workflow-plans.md) explains.

## `principles`: `concept-design`

**Daniel Jackson, "Concept Design Moves", 2022.** In *NASA Formal Methods, NFM 2022*,
Lecture Notes in Computer Science 13260, Springer, pages 52 to 70,
[doi:10.1007/978-3-031-06773-0_3](https://doi.org/10.1007/978-3-031-06773-0_3); the
author's copy, [nfm-design-moves-22.pdf](https://people.csail.mit.edu/dnj/publications/nfm-design-moves-22.pdf).

- Taken: what a concept is, after its section 2; the six moves in three pairs of duals,
  split and merge, unify and specialize, tighten and loosen; the quality that each gains
  and the one it costs; one software example per move; the limits that its section 6
  states.
- Where: [`SKILL.md`](../../plugins/principles/skills/concept-design/SKILL.md) of
  `concept-design`, whose test, `tests/packaging/test_concept_design.py`, takes the
  qualities from the paper; step 1 of `workflow:plans` names the skill.
- Departs: Jackson's concepts are what a user sees of a system, and he sets his moves
  apart from refactoring; shift-left applies them to the concepts of a code base. The
  signs for code, and the stance that leans towards fewer and sharper concepts where a
  trade-off is close, are shift-left's, not Jackson's.

**Daniel Jackson, *The Essence of Software: Why Concepts Matter for Great Design*,
2021.** Princeton University Press,
[press.princeton.edu/isbn/9780691230542](https://press.princeton.edu/isbn/9780691230542).

- Taken: the theory of concepts that the paper's moves build on.
- Where: the line "Sources" of `SKILL.md` of `concept-design` names it beside the paper.

## `workflow`: `plans`

**Kent Beck, "make the change easy", 2012.** A post on X, 25 September 2012, "for each
desired change, make the change easy (warning: this may be hard), then make the easy
change",
[x.com/KentBeck/status/250733358307500032](https://x.com/KentBeck/status/250733358307500032).

- Taken: the order of a move on a concept, which comes first so that the requested
  change is easy.
- Where: step 4 of [`SKILL.md`](../../plugins/workflow/skills/plans/SKILL.md), which
  quotes the maxim without naming its author, as the skill names no one;
  [About `workflow:plans`](../explanation/workflow-plans.md) names him.

**Kent Beck, *Tidy First? A Personal Exercise in Empirical Software Design*, 2023.**
O'Reilly Media, [oreilly.com/library/view/tidy-first/9781098151232](https://www.oreilly.com/library/view/tidy-first/9781098151232/).

- Taken: changes of structure kept apart from changes of behaviour, in commits of their
  own; tidying as an economic choice.
- Where: step 4's rule that the commits of a move on a concept change no behaviour.
- Departs: Beck's tidyings are small, and when to tidy is left to the programmer's
  judgement; a move on a concept may reach across many files, and `workflow:plans`
  allows one per plan, on a concept whose code the change edits, declared in a decision
  that the user approves.

Daniel Jackson's paper, above, gives the moves that step 1 of `workflow:plans` points to
through `concept-design`.

## `learning`: `learning-mode`

`learning-mode` was written from the owner's own rules and cites no source. The
techniques it uses have research behind them: these works are where a reader can check
them, not where the skill came from.

| Technique, and where `learning-mode` uses it | Work |
|---|---|
| A worked example before practice, step 3 | John Sweller and Graham A. Cooper, "The Use of Worked Examples as a Substitute for Problem Solving in Learning Algebra", *Cognition and Instruction* 2(1), 1985, [doi:10.1207/s1532690xci0201_3](https://doi.org/10.1207/s1532690xci0201_3) |
| Fading, from a worked example to an independent task, step 7 | Alexander Renkl and Robert K. Atkinson, "Structuring the Transition From Example Study to Problem Solving in Cognitive Skill Acquisition: A Cognitive Load Perspective", *Educational Psychologist* 38(1), 2003, [doi:10.1207/S15326985EP3801_3](https://doi.org/10.1207/S15326985EP3801_3) |
| Self-explanation questions, step 4 | Michelene T. H. Chi, Nicholas De Leeuw, Mei-Hung Chiu and Christian Lavancher, "Eliciting Self-Explanations Improves Understanding", *Cognitive Science* 18(3), 1994, [doi:10.1207/s15516709cog1803_3](https://doi.org/10.1207/s15516709cog1803_3) |
| Help given least first, and reduced as performance improves, steps 6 and 7 | David Wood, Jerome S. Bruner and Gail Ross, "The Role of Tutoring in Problem Solving", *Journal of Child Psychology and Psychiatry* 17(2), 1976, [doi:10.1111/j.1469-7610.1976.tb00381.x](https://doi.org/10.1111/j.1469-7610.1976.tb00381.x) |
| Cognitive debt, which the skill sets out to reduce | Nataliya Kosmyna and others, "Your Brain on ChatGPT: Accumulation of Cognitive Debt when Using an AI Assistant for Essay Writing Task", 2025, [arXiv:2506.08872](https://arxiv.org/abs/2506.08872) |

- Departs: the skill gives cognitive debt its own definition, the gap between an
  assistant's output and what the user can understand, handle and recreate alone. The
  paper, a study of 54 participants writing essays, found weaker brain connectivity and
  poorer recall of their own essays among those who wrote with a language model, and
  names that cost cognitive debt in its title.

## Commit messages

**Tim Pope, "A Note About Git Commit Messages", 2008.**
[tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html).

- Taken: a summary line of about 50 characters, in the imperative, and a body wrapped at
  72 columns.
- Where: the rules on commits of [`instructions/global.md`](../../instructions/global.md)
  and of step 4 of `workflow:plans`.
- Departs: shift-left makes 50 characters a limit, where Pope calls it no hard maximum.

## The documentation

**Daniele Procida, Diátaxis.** [diataxis.fr](https://diataxis.fr/).

- Taken: four kinds of documentation, tutorials, how-to guides, reference and
  explanation, one kind per page.
- Where: `docs/tutorials/`, `docs/how-to/`, `docs/reference/` and `docs/explanation/`,
  as [`AGENTS.md`](../../AGENTS.md) lays them out.

## Standards

- [Agent Skills](https://agentskills.io/specification): the format of every `SKILL.md`,
  which `tests/packaging/test_skills.py` checks.
- [Agent Plugins](https://agent-plugins.org/specification): the manifest `plugin.json`
  of each plugin that holds a skill, which `tests/packaging/test_manifests.py` checks.
- [JSON Schema](https://json-schema.org/draft/2020-12/schema), draft 2020-12: the schema
  of a finding of `coordinator`, `finding.schema.json`, written in the subset that
  `findings.py` checks.

## Evidence of shift-left's own

Several rules of `workflow:plans`, among them the critics of step 2, the short plans and
the bound on rounds of review, rest on the owner's measurements of plans and reviews in
shift-left and in other repositories. The move on a concept rests on the owner's
conviction that fewer and sharper concepts make every later change cheaper, as
[About `workflow:plans`](../explanation/workflow-plans.md) says; research that the owner
made in November 2026 shaped its bounds, small diffs and a consolidation that is a
reviewable change of its own, and found concept design its closest relative, with thin
evidence. Neither the measurements nor the research is published. `learning-mode` was
written from the owner's own rules and names no source. What was observed of each
client is recorded in [`docs/harness-facts.md`](../harness-facts.md).
