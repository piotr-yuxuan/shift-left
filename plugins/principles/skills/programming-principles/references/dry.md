# DRY: Don't Repeat Yourself

[All programming principles](../SKILL.md)

**Definition:** Give each business rule, fact or design decision one
authoritative representation within its intended scope. Derive other
representations when possible. Duplication matters when a change to one piece
of knowledge requires synchronised changes in several places; identical text
can express independently owned knowledge.

## Example 1: one delivery threshold, two inconsistent answers

**Circumstance:** The free-delivery threshold changes from 5,000 to 6,000 pence.
The basket message and checkout charge must agree.

**Bad:** Only one of two copied thresholds is updated. **Good:** Both consumers
use the same policy.

```python
def bad_basket_message(total):
    return "Free delivery" if total >= 5_000 else "Delivery charged"


def bad_checkout_delivery(total):
    return 0 if total >= 6_000 else 500


assert bad_basket_message(5_500) == "Free delivery"
assert bad_checkout_delivery(5_500) == 500  # Contradicts that message.

FREE_DELIVERY_THRESHOLD = 6_000


def qualifies_for_free_delivery(total):
    return total >= FREE_DELIVERY_THRESHOLD


message = "Free delivery" if qualifies_for_free_delivery(5_500) else "Delivery charged"
charge = 0 if qualifies_for_free_delivery(5_500) else 500
assert (message, charge) == ("Delivery charged", 500)
```

## Example 2: storing an easily derived total

**Circumstance:** A basket has at most twenty lines. Calculating the sum is cheap.

**Bad:** A stored total can disagree with its source values. **Good:** Derive the
total whenever it is requested.

```python
basket = {"prices": [400, 600], "total": 1_000}
basket["prices"].append(300)
assert basket["total"] == 1_000
assert sum(basket["prices"]) == 1_300  # The cached copy is stale.

prices = [400, 600, 300]
assert sum(prices) == 1_300
```

**Better under a different circumstance:** If measurement establishes that
recalculation is expensive, a cache may be justified. One owner must then
maintain or invalidate it whenever its source changes. The extra representation
creates an explicit consistency obligation.

**Review question:** If this rule changes tomorrow, how many independently
maintained representations must change with it?

## References

Hunt and Thomas, [The Evils of Duplication](https://media.pragprog.com/titles/tpp20/dry.pdf).
