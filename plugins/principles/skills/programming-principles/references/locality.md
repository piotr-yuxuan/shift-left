# Locality of behaviour and reasoning

[All programming principles](../SKILL.md)

**Definition:** Arrange code so that understanding an operation requires reading
a small, identifiable set of declarations and contracts. Keep facts that must
be considered together close together, and make the operation's dependencies
and effects visible. Locality concerns the reader's required context; placing
everything in one file does not establish it.

Keep an invariant's validation and state transitions close to its owner. Avoid
parallel collections coupled by position, hidden mutation and undocumented call
order. Pass the values an operation needs instead of a mutable context bag.

## Example 1: hidden preparation versus explicit values

**Circumstance:** A price is the subtotal minus a previously agreed discount.
Both values are non-negative integer pence and the discount cannot exceed the
subtotal.

**Bad:** The caller must know that another function has already inserted a
particular key into a mutable dictionary. **Good:** The function receives the
two values its calculation needs.

```python
def bad_total(context):
    return context["subtotal"] - context["prepared_discount"]


context = {"subtotal": 2_000}
try:
    bad_total(context)
except KeyError as error:
    assert error.args == ("prepared_discount",)
else:
    raise AssertionError("The hidden preparation dependency disappeared")


def total_pence(subtotal_pence, discount_pence):
    return subtotal_pence - discount_pence


assert total_pence(2_000, 300) == 1_700
```

The good call contains the information needed to understand the calculation.
It does not require reconstructing an earlier sequence of mutations.

## Example 2: related policy scattered across files

**Circumstance:** Standard delivery has one charge and one eligibility rule.
The warehouse team changes these together.

```text
Bad: understanding standard delivery requires finding unrelated locations.
  settings.py:                 STANDARD_DELIVERY_PENCE = 500
  utils.py:                    standard_delivery_is_available(postcode)
  checkout/helpers.py:         exception for collection-only products

Good: the delivery policy has an identifiable home.
  delivery/standard.py:        charge, eligibility and product restrictions
  checkout.py:                 calls the standard delivery policy

Also good when several entrypoints use it:
  checkout.py and telephone_orders.py call that same policy module.
```

The policy's callers can remain separate. Copying the policy into every caller
would improve physical proximity while creating a maintenance problem.

**Review question:** Which other locations must I inspect to explain this
operation, and which of those dependencies could be made explicit or local?

## References

Carson Gross, [Locality of Behaviour](https://htmx.org/essays/locality-of-behaviour/).
