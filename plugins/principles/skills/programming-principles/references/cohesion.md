# High cohesion

[All programming principles](../SKILL.md)

**Definition:** Put elements in the same unit when they jointly implement one
coherent concept, behaviour or invariant. A cohesive unit has a specific purpose
that explains why its contents belong together. Sharing a programming language,
being short or having no other obvious home is insufficient.

## Example 1: a generic utility collection

**Circumstance:** Money formatting, password verification and parcel dimensions
have different rules and owners.

```text
Bad:
  utils.py
    format_pence
    verify_password
    parcel_volume
    choose_delivery_box

Good:
  money.py       -> format_pence
  identity.py    -> verify_password
  packaging.py   -> parcel_volume, choose_delivery_box
```

Parcel volume and box selection stay together because the latter uses the
former to answer the same packaging question. Moving every function into its
own file would lose that relationship without establishing a new benefit.

## Example 2: values joined only by matching positions

**Circumstance:** Each product has one price. Sorting product names must not
silently attach a different price to a product.

**Bad:** Two independently mutable lists carry an undocumented alignment rule.
**Good:** Each key is stored with its own value.

```python
names = ["tea", "coffee"]
prices = [300, 500]
names.sort()
bad_catalogue = dict(zip(names, prices, strict=True))
assert bad_catalogue["coffee"] == 300  # Coffee should cost 500.

catalogue = {"tea": 300, "coffee": 500}
display_rows = sorted(catalogue.items())
assert display_rows == [("coffee", 500), ("tea", 300)]
```

This applies cohesion to data: the product-price relationship is maintained by
the representation, so the reader need not coordinate two separate structures.

**Review question:** What single concept explains why these elements belong
together, and which invariant would be harder to maintain if they were split?

## References

Robert C. Martin, [The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html),
including its discussion of cohesion and coupling.
