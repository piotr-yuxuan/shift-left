# YAGNI: You Aren't Gonna Need It

[All programming principles](../SKILL.md)

**Definition:** Implement capabilities required by the current agreed scope;
defer capabilities whose only justification is that they might be needed later.
This includes speculative extension mechanisms. Work needed for present
correctness, safety, verification and understandable structure remains part of
the current requirement.

## Example 1: one input format

**Circumstance:** A local tool accepts JSON arrays of names. There is no
requirement for plugins or additional formats.

**Bad for this scope:** Define a plugin registry, abstract loader, dynamic
import convention and factory before loading any data. **Good:** Implement the
required format and reject the wrong data shape.

```python
import json


def load_names(source):
    names = json.loads(source)
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("Expected a JSON array of names")
    return names


assert load_names('["Ada", "Grace"]') == ["Ada", "Grace"]
try:
    load_names('{"name": "Ada"}')
except ValueError:
    pass
else:
    raise AssertionError("An object is outside the input contract")
```

Input validation serves the current contract, so omitting it would not be a
useful application of YAGNI.

## Example 2: the requirement actually expands

**Circumstance:** Users now need JSON arrays and one-name-per-line text. A text
line is trimmed; empty lines are ignored.

**Good now:** Add the second supported format explicitly. **Still excessive:**
Introduce third-party plugin discovery without a requirement for third-party
extensions.

```python
import json


def load_names(source, format_name):
    if format_name == "json":
        names = json.loads(source)
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError("Expected a JSON array of names")
        return names
    if format_name == "lines":
        return [line.strip() for line in source.splitlines() if line.strip()]
    raise ValueError(f"Unsupported format: {format_name}")


assert load_names('["Ada", "Grace"]', "json") == ["Ada", "Grace"]
assert load_names("Ada\n\n Grace \n", "lines") == ["Ada", "Grace"]
```

The same simplicity principle leads to different code after a real requirement
change. YAGNI permits improving the structure so subsequent changes remain easy.

**Review question:** Which current acceptance example requires this capability
or extension point?

## References

Martin Fowler, [YAGNI](https://martinfowler.com/bliki/Yagni.html).
