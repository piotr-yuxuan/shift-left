# Separation of concerns

[All programming principles](../SKILL.md)

**Definition:** Give distinct concerns boundaries that let a person reason about
or change one concern without also reasoning about the implementation of the
others. A concern is a coherent question, such as what a customer owes, how a
result is displayed or how it is stored. Separate files alone do not create
independent concerns.

Before implementation, identify business decisions, external I/O, resource
ownership and atomic state changes. Describe the normal path and failure
transitions. Challenge constraints that force unrelated responsibilities
together, including arbitrary limits on functions, classes or files.

Separate policy, orchestration and mechanisms: decisions operate on explicit
values without I/O; orchestration shows the meaningful sequence; HTTP, SQL and
serialisation details stay behind small, concrete interfaces. Introduce only
boundaries needed now; frameworks, repositories and class hierarchies are not
prerequisites. Separating concerns does not require a helper for every step.

## Example 1: pricing and presentation

**Circumstance:** Members receive a 100-pence discount on prices of at least
100 pence. Both a receipt and a structured API response need that price.
Pricing and presentation change independently.

**Bad:** Each new presentation duplicates pricing decisions. **Good:** The
pricing function produces a value that different presentations can use.

```python
def bad_receipt(price_pence, member):
    amount = price_pence - 100 if member else price_pence
    return f"Amount due: {amount} pence"


def amount_due(price_pence, member):
    return price_pence - 100 if member else price_pence


receipt = f"Amount due: {amount_due(1_000, True)} pence"
response = {"amount_due_pence": amount_due(1_000, True)}
assert receipt == bad_receipt(1_000, True)
assert response == {"amount_due_pence": 900}
```

The two presentations share an existing pricing rule; their one-off formatting
stays inline. Changing the receipt wording leaves that rule alone. A function
boundary is sufficient; a class hierarchy is unnecessary for this example.

## Example 2: splitting by technology can preserve entanglement

**Circumstance:** An order total must obey the same pricing rules on a website
and in a scheduled invoice job.

| Arrangement | Consequence |
| --- | --- |
| **Bad:** `web.py` and `batch.py` each calculate discounts, query storage and format their own output. | There are two files, but pricing changes still require understanding both entrypoints. |
| **Good:** A pricing function accepts order values and returns the amount; the entrypoints load data and format the result. | Both entrypoints use the same decision without knowing its implementation. |
| **Excessive for this requirement:** Every arithmetic step receives its own service, interface and factory. | The new boundaries add concepts without separating independently meaningful concerns. |

**Review question:** Can I change the presentation without understanding the
pricing implementation, and vice versa?

## References

Dijkstra, [On the role of scientific thought](https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html).
