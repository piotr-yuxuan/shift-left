# Information hiding

[All programming principles](../SKILL.md)

**Definition:** Assign a design decision to a module and expose a contract that
does not require callers to know that decision. The hidden knowledge can be a
data structure, algorithm, encoding or storage mechanism. The module must also
preserve the invariants promised by its public operations.

## Example 1: exposing the collection used for membership

**Circumstance:** Several consumers need to record whether an identifier has
been seen through a stable public contract. Ordering and duplicate counts are
outside this contract.

**Bad:** Callers manipulate the chosen list directly. **Good:** Callers use
operations whose meanings survive a change of representation.

```python
bad_seen_ids = []
bad_seen_ids.append("a")
assert "a" in bad_seen_ids


class SeenIds:
    def __init__(self):
        self._ids = set()

    def record(self, identifier):
        self._ids.add(identifier)

    def contains(self, identifier):
        return identifier in self._ids


seen = SeenIds()
seen.record("a")
seen.record("a")
assert seen.contains("a")
assert not seen.contains("b")
```

Callers no longer depend on `append`, indexing or iteration order. Python's
underscore is a convention, not access control: a caller that reaches into
`_ids` reintroduces the dependency.

For one local calculation with no such public contract, using a set directly
may be sufficient. The wrapper earns its place through that boundary.

## Example 2: hiding a storage decision without hiding failures

**Circumstance:** A report can initially be read from a UTF-8 text file and later
from compressed storage. Callers need the report's text.

```text
Bad public contract:
  locate_report_path(id) -> a path callers open and decode themselves
  Callers depend on filesystem access, encoding and compression choices.

Good public contract for these callers:
  read_report_text(id) -> text
  Raises ReportNotFound when absent and ReportUnavailable on storage failure.
  The implementation owns locating, opening, decoding and closing the data.
```

The interface must still disclose meaningful behaviour, including failures and
resource obligations. Hiding necessary semantics would make callers less able
to use it correctly. A streaming interface may be preferable when reports are
too large to load into memory; that changes the resource contract explicitly.

**Review question:** Which design decision can I change inside this module
without changing its callers, and what promises must remain true?

## References

Parnas, [On the Criteria To Be Used in Decomposing Systems into Modules](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html).
