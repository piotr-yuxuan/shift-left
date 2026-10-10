# Low cyclomatic complexity

[All programming principles](../SKILL.md)

**Definition:** Keep the number of independent control-flow paths within a
function small enough to understand and verify. For a connected control-flow
graph with one entry and one exit, McCabe complexity is `E - N + 2`, where `E`
counts edges and `N` counts nodes; with only binary decisions it is the number
of decision nodes plus one. This metric does not measure
naming quality, hidden state, nesting depth or coupling.

Ruff enforces the repository's McCabe threshold of 10 with `C901`. Meeting it
still requires judgement about the resulting design and tests. Do not suppress
checks or move complexity between functions merely to satisfy the metric.

For loops, identify the progress measure and termination condition. Prefer an
iterator or explicit condition when it expresses the algorithm. Use `while True`
only when it improves clarity and its exit paths are local and evident.
Externally controlled iteration needs appropriate bounds: an operation-wide
deadline and attempt, page, byte or record limits according to the task. A
per-request timeout does not establish an operation-wide deadline.

## Example 1: flatter control flow with the same score

**Circumstance:** Shipping requires an active account, an address and positive
stock. Inputs are booleans and an integer stock count.

**Bad for readability:** The reader carries three nested conditions.
**Better:** Each rejection is explicit. Both functions have three binary
decisions and cyclomatic complexity 4.

```python
def nested_can_ship(active, has_address, stock):
    if active:
        if has_address:
            if stock > 0:
                return True
    return False


def flat_can_ship(active, has_address, stock):
    if not active:
        return False
    if not has_address:
        return False
    if stock <= 0:
        return False
    return True


for active in (False, True):
    for has_address in (False, True):
        for stock in (0, 1):
            expected = (active, has_address, stock) == (True, True, 1)
            assert nested_can_ship(active, has_address, stock) == expected
            assert flat_can_ship(active, has_address, stock) == expected
```

This improves comprehension without lowering the score. Three sequential,
independent binary decisions can also permit eight outcome combinations even
though their cyclomatic complexity is only four.

## Example 2: a lookup expressed as repeated branching

**Circumstance:** Four external status strings map to four internal strings.
Unknown strings must map to `unknown`; no transition has side effects.

**Bad fit:** Repeated branching obscures a simple mapping. **Good:** Represent
the mapping directly as data.

```python
def branched_status(status):
    if status == "new":
        return "queued"
    if status == "working":
        return "running"
    if status == "finished":
        return "done"
    if status == "broken":
        return "failed"
    return "unknown"


STATUS_NAMES = {"new": "queued", "working": "running", "finished": "done", "broken": "failed"}


def mapped_status(status):
    return STATUS_NAMES.get(status, "unknown")


for source, expected in [
    ("new", "queued"),
    ("working", "running"),
    ("finished", "done"),
    ("broken", "failed"),
    ("?", "unknown"),
]:
    assert branched_status(source) == mapped_status(source) == expected
```

The functions have complexities 5 and 1 under ordinary decision counting.
Every mapping still needs verification. Moving policy into data does not remove
the policy's possible mistakes or justify hiding complicated actions in a table.

**Review question:** Did this change simplify the decisions, or merely move
them somewhere the metric does not inspect?

## References

Watson and McCabe, [Structured Testing](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication500-235.pdf),
especially sections 2.3, 2.5 and 4.1; [Ruff C901](https://docs.astral.sh/ruff/rules/complex-structure/).
