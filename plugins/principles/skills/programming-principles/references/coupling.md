# Low coupling

[All programming principles](../SKILL.md)

**Definition:** Limit the assumptions one component makes about another
component's representation, implementation, timing and environment. Necessary
dependencies should pass through explicit, narrow contracts. Coupling is low
when changing a private detail rarely forces unrelated consumers to change.

## Example 1: passing an entire nested object

**Circumstance:** A delivery calculation needs only a country code. GB delivery
costs 500 pence and every other supported country costs 900 pence.

**Bad:** The calculation depends on the order's customer-address layout.
**Good:** The calculation receives the country directly.

```python
def coupled_delivery(order):
    country = order["customer"]["address"]["country"]
    return 500 if country == "GB" else 900


def delivery_pence(country):
    return 500 if country == "GB" else 900


order = {"customer": {"address": {"country": "GB"}}}
assert coupled_delivery(order) == 500
assert delivery_pence("GB") == 500

new_order_shape = {"destination_country": "GB"}
assert delivery_pence(new_order_shape["destination_country"]) == 500
```

The entrypoint still understands the order representation. The pricing decision
no longer needs that knowledge. The boundary concentrates an unavoidable
dependency rather than making it disappear.

## Example 2: callers tied to a provider's response format

**Circumstance:** A carrier changes its response from
`{"quote": {"pence": 500}}` to `{"amount_minor": 500}`.

| Design | Work required by the provider change |
| --- | --- |
| **Bad:** Checkout, reporting and telephone sales each inspect the carrier's JSON. | All three consumers need edits and must understand the external schema. |
| **Good:** A carrier adapter returns a documented integer amount in pence. | The adapter's parser and its schema tests change; consumers retain their contract. |
| **Unhelpful abstraction:** An adapter returns the raw JSON under a different name. | The same schema dependency still reaches every consumer. |

This boundary is justified by a concrete external contract. It does not require
a universal interface for every conceivable carrier.

**Review question:** Which assumptions about another component would force this
code to change if that component were replaced?

## References

Parnas, [On the Criteria To Be Used in Decomposing Systems into Modules](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html).
