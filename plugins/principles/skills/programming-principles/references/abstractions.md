# Abstractions should reduce mental effort

[All programming principles](../SKILL.md)

**Definition:** Introduce an abstraction when its contract lets callers perform
a meaningful operation while understanding fewer implementation details. Assess
both the complexity hidden and the concepts added by the interface. A shorter
caller is insufficient if understanding it requires following several equally
complicated wrappers.

In this repository, do not introduce single-use helper functions or methods.
Keep one-off steps inline. Extract shared logic only when existing production
callers need the same operation and the abstraction reduces maintenance burden;
test calls do not count as reuse. Each function must have a coherent contract
and a consistent level of abstraction. Arbitrary fragments, forwarding wrappers
and generic utility modules need a demonstrated benefit.

## Example 1: a library hides a real parsing problem

**Circumstance:** A CSV field can contain a comma inside quotes.

**Bad:** Splitting on commas gives the wrong fields. **Good:** The standard CSV
parser implements the quoting rules behind a small interface.

```python
import csv
from io import StringIO

source = 'name,city\n"Doe, Jane",York\n'
bad_fields = source.splitlines()[1].split(",")
assert bad_fields == ['"Doe', ' Jane"', "York"]

records = list(csv.DictReader(StringIO(source)))
assert records == [{"name": "Doe, Jane", "city": "York"}]
```

The abstraction removes knowledge the caller would otherwise need: quoting,
delimiters and field decoding. Its benefit is larger than a change of name.

## Example 2: naming an operation versus adding forwarding layers

**Circumstance:** A report needs the sum of integer prices once, with no extra
business rules.

```python
def calculate_total(values):
    return forward_total(values)


def forward_total(values):
    return perform_total(values)


def perform_total(values):
    return sum(values)


assert calculate_total([200, 300]) == 500
assert sum([200, 300]) == 500
```

**Bad for this circumstance:** The three wrappers add navigation and names but
hide no relevant decision. **Good:** Use `sum(prices)` directly.

**Better under a different circumstance:** Invoice previews and issued invoices
both need the same rounding, discount and tax-ordering policy. A shared
`invoice_total(lines)` can own that operation for those existing production
callers. Its contract removes policy details they would otherwise duplicate;
hypothetical future reuse does not justify extracting it.

**Review question:** What can the caller safely stop knowing because this
abstraction exists?

## References

John Ousterhout, [Managing Complexity](https://web.stanford.edu/~ouster/cgi-bin/cs190-spring15/lecture.php?topic=complexity).
