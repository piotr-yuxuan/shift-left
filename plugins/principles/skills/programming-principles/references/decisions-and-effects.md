# Separate decisions from effects

[All programming principles](../SKILL.md)

**Definition:** Express decisions as calculations over explicit values, and
place interactions with the external world in an orchestration boundary. The
decision code returns values describing its result; surrounding code obtains
inputs and performs required effects. Time, randomness, files, databases and
network calls are dependencies that must be accounted for.

## Example 1: the clock is an input to a policy

**Circumstance:** An invoice is overdue strictly after its due date. The policy
uses calendar dates; timezone selection belongs to the caller obtaining today.

**Bad for repeatable reasoning:** The decision reads the system clock itself.
**Good:** Pass the date used by the decision.

```python
from datetime import date


def clock_dependent_overdue(due_date):
    return due_date < date.today()


def is_overdue(due_date, today):
    return due_date < today


assert not is_overdue(date(2026, 10, 3), date(2026, 10, 3))
assert is_overdue(date(2026, 10, 3), date(2026, 10, 4))
```

The decision can now be checked for any date without replacing the clock or
waiting until tomorrow. The real entrypoint obtains today's date once.

## Example 2: deciding which notices to send

**Circumstance:** A batch selects unpaid, overdue invoices. Each invoice is an
`(identifier, due_date, paid)` tuple. Delivery is a separate operation.

**Bad:** Selection branches and delivery calls are interleaved, so inspecting
the selection requires accounting for an external dependency. **Good:** Calculate
the selected identifiers before delivery, keeping this one-off selection inline.

```python
from datetime import date


invoices = [
    ("A", date(2026, 10, 1), False),
    ("B", date(2026, 10, 1), True),
    ("C", date(2026, 10, 5), False),
]
today = date(2026, 10, 3)
selected = [
    identifier
    for identifier, due_date, paid in invoices
    if not paid and due_date < today
]
assert selected == ["A"]

delivered = []  # An in-memory stand-in for this worked example's delivery.
for identifier in selected:
    delivered.append(identifier)
assert delivered == ["A"]
```

Selection tests establish the policy. Real delivery still needs its own failure
and retry contract: a failure halfway through sending must not be mistaken for
an atomic batch. Before adding retries, account for idempotency and partial
effects, and bound attempts and total duration. Separation exposes these
responsibilities; it does not solve them or require a single-use helper.

**Review question:** Can I evaluate the decision using ordinary values without
accessing the clock, network or database?

## References

Gary Bernhardt, [Functional Core, Imperative Shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell).
