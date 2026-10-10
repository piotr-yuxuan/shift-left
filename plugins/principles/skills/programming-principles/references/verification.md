# Design for meaningful verification

[All programming principles](../SKILL.md)

**Definition:** Make important contracts observable and verify them against
expectations derived independently of the implementation. Tests should reject
plausible incorrect implementations, cover relevant failure boundaries and
permit internal restructuring that preserves the tested contract. A passing
test establishes only the properties it actually exercises.

Verify design properties as well as outputs: resource release, transaction
atomicity, bounded retries, meaningful interleavings and behaviour under
dependency failure where applicable. Derive expected results independently of
production constants and logic. For each important guarantee, name a plausible
incorrect implementation that the test must reject.

## Example 1: copying the production formula into the expectation

**Circumstance:** The agreed discount is exactly 10% on amounts divisible by
100. Production accidentally uses 20%.

**Bad:** The test copies the production constant and formula, so both share the
same mistake. **Good:** Use concrete expected results from the requirement.

```python
PRODUCTION_DISCOUNT_PERCENT = 20  # A deliberate production bug.


def buggy_price(amount):
    return amount - amount * PRODUCTION_DISCOUNT_PERCENT // 100


# Bad verification: this passes despite the wrong policy.
assert buggy_price(1_000) == 1_000 - 1_000 * PRODUCTION_DISCOUNT_PERCENT // 100


def check_ten_percent_contract(price_function):
    assert price_function(1_000) == 900
    assert price_function(2_000) == 1_800


# Show that the independent contract rejects the plausible mistake.
try:
    check_ten_percent_contract(buggy_price)
except AssertionError:
    pass
else:
    raise AssertionError("The contract failed to detect the wrong discount")


def correct_price(amount):
    return amount - amount // 10


check_ten_percent_contract(correct_price)
```

The test data deliberately retains the agreed values. Reusing the implementation
to derive its own expected result would remove that independent check.

## Example 2: observable behaviour versus an internal call sequence

**Circumstance:** Name normalisation trims surrounding whitespace and lowercases
letters. Whether trimming happens before lowercasing is outside the contract
because the operations commute for these inputs.

**Bad:** Require a private helper to run, or require an exact internal call
sequence. **Good:** Check the output through the public operation.

```python
def normalise_name_v1(name):
    return name.strip().lower()


def normalise_name_v2(name):
    return name.lower().strip()


examples = [(" Ada ", "ada"), ("GRACE", "grace"), ("   ", "")]
for normalise in (normalise_name_v1, normalise_name_v2):
    for source, expected in examples:
        assert normalise(source) == expected
```

Both implementations satisfy these examples. A test that insists on “strip
before lower” would reject an acceptable change. Conversely, interaction order
is worth testing when it is part of the contract, such as authorising a request
before writing data. Resource release and transaction atomicity also require
checks beyond returned values.

**Review question:** Name an implementation that would violate the requirement.
Would this test fail for it, and would it still pass after a harmless refactoring?

## References

Google, [Test Behaviors, Not Methods](https://testing.googleblog.com/2014/04/testing-on-toilet-test-behaviors-not.html)
and [Effective Testing](https://testing.googleblog.com/2014/05/testing-on-toilet-effective-testing.html).
