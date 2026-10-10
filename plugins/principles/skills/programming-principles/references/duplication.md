# Prefer duplication over the wrong abstraction

[All programming principles](../SKILL.md)

**Definition:** Keep similar implementations separate when they represent
different concepts or change for independent reasons, and sharing them would
force unrelated callers to coordinate. Extract common code when there is a
stable shared contract. Similar syntax alone does not establish that contract.

## Example 1: two percentages with different owners

**Circumstance:** A loyalty rebate and an environmental levy both start at 10%.
The marketing team raises only the rebate to 20%. Amounts in this example are
multiples of 100 pence, so rounding is irrelevant.

**Bad:** Both concepts use a shared function whose percentage is changed.
**Good:** Each policy can change independently.

```python
def bad_shared_adjustment(amount):
    return amount // 5  # Changed to 20% for the rebate.


rebate = bad_shared_adjustment(1_000)
levy = bad_shared_adjustment(1_000)
assert (rebate, levy) == (200, 200)  # The levy should remain 100.


def loyalty_rebate(amount):
    return amount // 5


def environmental_levy(amount):
    return amount // 10


assert (loyalty_rebate(1_000), environmental_levy(1_000)) == (200, 100)
```

A shared arithmetic operation such as percentage multiplication may still be
useful. The independently owned policy rate must not become one shared fact.

## Example 2: a formatter accumulates incompatible modes

**Circumstance:** One export targets spreadsheets; another targets HTML pages.
CSV quoting and HTML escaping obey different contracts.

```text
Bad evolving abstraction:
  export(rows, html=False, quote_commas=True, escape_tags=False,
         include_header=True, use_table_tags=False)
  Several combinations of flags make no sense.

Good separate operations:
  export_csv(rows)    -> CSV text with CSV quoting
  render_html(rows)   -> HTML with HTML escaping

Good shared part, if both require the same business ordering:
  ordered_report_rows(records) -> values in the agreed order
  Each output operation consumes those values independently.
```

Splitting the formatters removes irrelevant choices from each caller. Keeping
the shared ordering rule preserves DRY where the knowledge really is shared.

**Review question:** Would a legitimate change for one caller be an unwanted
change for another, and are flags compensating for that mismatch?

## References

Sandi Metz, [The Wrong Abstraction](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction).
