---
name: programming-principles
description: Design rules for clear, maintainable, verifiable code - locality, separation of concerns, DRY, low complexity, cohesion, coupling, single responsibility, information hiding, useful abstractions, duplication over the wrong abstraction, YAGNI, decisions separate from effects, explicit invariants, resource ownership, readability, meaningful verification - plus rules for code that calls a language model. Use before the first edit whenever writing, refactoring, debugging, reviewing or testing code, and whenever a design decision is being made.
---

# Programming principles

Good design reduces the knowledge required to understand an operation, change
it safely and verify its behaviour. Optimise for the context a maintainer must
hold, not for short files or passing tests: neither establishes good design.
These principles address different sources of difficulty; they are not a score
to maximise mechanically. When two conflict, name the trade-off and choose
explicitly. A repository's own rules and linters take precedence; flag conflicts.

## Before the first edit

Identify, in a few lines: the decisions (business rules), the external I/O, the
resources acquired and their owner, the changes that must be atomic, and the
normal and failure paths. State the simplest viable design and why anything
more is needed. For a refactoring, name the maintenance problem first and how
behaviour preservation will be shown.

## The principles

Each line gives the rule and when to open its guide. Read a guide when a
decision depends on it; do not load them all routinely. Each guide has a
definition, two worked examples, a review question and references.

- [Locality](references/locality.md): keep related knowledge together and
  dependencies explicit. Open when logic or configuration is spread across files.
- [Separation of concerns](references/concerns.md): separate independently
  changing concerns. Open when one module mixes parsing, policy, I/O and output.
- [DRY](references/dry.md): give each business rule one authoritative
  representation. Open when the same rule appears twice.
- [Low complexity](references/complexity.md): make control flow, progress and
  termination evident. Open for nested branches, loops with exits, retries.
- [High cohesion](references/cohesion.md): group operations that serve the same
  purpose. Open when deciding where code belongs.
- [Low coupling](references/coupling.md): depend on narrow, explicit contracts.
  Open when a change ripples, or a caller needs another module's internals.
- [Single responsibility](references/responsibility.md): separate reasons to
  change. Open when a unit has two audiences or two change cadences.
- [Information hiding](references/information-hiding.md): keep changeable
  details behind contracts. Open when exposing a format, a vendor or a layout.
- [Useful abstractions](references/abstractions.md): an abstraction must reduce
  what callers must understand. Open before adding a class, protocol or layer.
- [Duplication over the wrong abstraction](references/duplication.md): prefer
  repetition to coupling unrelated rules. Open before merging look-alike code.
- [YAGNI](references/yagni.md): implement present requirements, no speculative
  machinery. Open before adding options, hooks or generality.
- [Decisions and effects](references/decisions-and-effects.md): keep business
  decisions free of I/O; time, randomness, files, network are inputs. Open when
  logic reads the clock, the environment, a file or the network.
- [Explicit invariants](references/invariants.md): give valid state and its
  transitions one owner; parse untrusted input at the boundary. Open when a
  value can be invalid, or flags can contradict each other.
- [Resource ownership](references/resources.md): minimise lifetimes and
  guarantee release on success, failure and interruption. Open for processes,
  files, connections, locks, transactions, threads and temporary directories.
- [Readability](references/readability.md): make intent, units and failure
  contracts explicit. Open when naming, positional data or error contracts are
  unclear.
- [Meaningful verification](references/verification.md): reject plausible
  defects with expectations derived independently of the implementation. Open
  before writing or judging any test.

## Constraints

- **No single-use helper functions or methods.** Keep one-off steps inline.
  Extract shared logic only for existing production callers when it reduces
  maintenance burden. Test calls do not count as reuse.
- **Cyclomatic (McCabe) complexity at most 10** for every new or changed
  function. Never move complexity between functions merely to satisfy the
  metric, and never suppress the check. In existing code, never make a
  function more complex; report pre-existing excess rather than fixing it out
  of scope. A function that genuinely needs more (a flat dispatch table, a
  parser) is a decision to justify to the user, not to hide.
- **Bound externally controlled work**: operation deadlines plus attempt, page,
  byte or record limits. A per-request timeout alone is not a bound. Account
  for idempotency and partial effects before retrying.
- **Keep transactions and locks clear** of unrelated network I/O, retry delays
  and user interaction.

## Code that calls a language model

- Model output is untrusted input. Parse it strictly at the boundary; let
  deterministic code decide legality or correctness; a failed or rejected call
  never changes state.
- Put the model behind a narrow port with one adapter and a scripted fake;
  tests run without network, keys or quota. Keep one opt-in live test.
- Bound every loop around the model: timeout per call, repair attempts per
  step, steps per task. State the worst case in calls and seconds.
- Classify failures: rejected reply (repair, then give up), unreachable model
  (abort; not a result), programming error (fail loudly).
- Measure before tuning: fixed seeds or cases, repeated trials, a
  deterministic baseline, the model and prompt version recorded with every
  number, and failing traces read before any change.
- Check provider documentation for SDK and API details instead of recalling them.

## When reviewing

Find what the change introduced or worsened. For each finding give the location,
the principle, a concrete consequence (a reading, change or failure scenario),
and what would resolve it. Distinguish a demonstrated defect, missing evidence
and an unsettled requirement. Name a plausible wrong implementation the tests
would still pass. Repeated code can be clearer than an abstraction; fewer lines
alone is not a benefit.
