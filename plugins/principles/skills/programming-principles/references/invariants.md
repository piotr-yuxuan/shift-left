# Represent invariants explicitly

[All programming principles](../SKILL.md)

**Definition:** Choose representations and construction rules that preserve
facts the rest of the program relies on. An invariant is a condition that must
hold for every valid instance or permitted state transition. Validate external
representations at the boundary, then carry the established guarantee forward
in the resulting value. Python annotations alone do not enforce runtime validity.

Give each invariant one owner and keep its validation and state transitions
together. Parse untrusted representations at boundaries, using precise internal
types for records and outcomes. Preserve malformed source information when later
validation requires it instead of discarding evidence during parsing.

## Example 1: validation that callers can immediately undo

**Circumstance:** A quantity must be a strictly positive integer; booleans are
not accepted as quantities.

**Bad:** Validate a dictionary once and let later code freely overwrite its
contents. **Good:** Construct a value that validates itself and resists ordinary
field reassignment.

```python
from dataclasses import FrozenInstanceError, dataclass

bad_order = {"quantity": 2}
assert bad_order["quantity"] > 0
bad_order["quantity"] = -3
assert bad_order["quantity"] < 0  # Earlier validation no longer protects us.


@dataclass(frozen=True)
class Quantity:
    value: int

    def __post_init__(self):
        if type(self.value) is not int or self.value <= 0:
            raise ValueError("Quantity must be a positive integer")


quantity = Quantity(2)
for invalid in (0, -3, True, 2.5):
    try:
        Quantity(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Invalid quantity accepted: {invalid!r}")

try:
    quantity.value = -3
except FrozenInstanceError:
    pass
else:
    raise AssertionError("Ordinary mutation must be rejected")
assert quantity.value == 2
```

This is an illustrative value type. Python offers deliberate escape hatches;
the guarantee covers normal construction and use of the public interface.
Applications can enforce the same boundary with their established model tools.

## Example 2: two flags permit contradictory states

**Circumstance:** A job is exactly one of queued, running or finished.

**Bad:** Independent flags permit “running and finished”. **Good:** Represent
the mutually exclusive alternatives as one state and parse unknown input
through that representation.

```python
from enum import Enum

bad_job = {"running": True, "finished": True}
assert bad_job["running"] and bad_job["finished"]


class JobState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"


state = JobState("running")
assert state is JobState.RUNNING
try:
    JobState("running_and_finished")
except ValueError:
    pass
else:
    raise AssertionError("Contradictory state must be rejected")
```

The enum constrains available states. A separate transition rule is still
needed if, for example, moving from finished back to running is forbidden.

**Review question:** Which invalid situation is currently representable, and
can the boundary prevent it instead of asking every consumer to detect it?

## References

Alexis King, [Parse, don't validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/),
and Python's [dataclass documentation](https://docs.python.org/3/library/dataclasses.html)
for the value type used in the example.
