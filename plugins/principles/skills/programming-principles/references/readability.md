# Readability and explicitness

[All programming principles](../SKILL.md)

**Definition:** Express intent, units, dependencies, effects and failures so a
reader can determine what the code does with minimal guessing. Prefer names and
structures that reveal the actual contract. Conciseness helps when it removes
distraction; compressed expressions and unexplained conventions can increase
the information the reader must reconstruct.

Distinguish invalid input, operational failure and programming defects. Catch
exceptions where recovery or translation is owned; do not make a failed
operation look successful. Use precise types for records and outcomes so that
callers can understand both success and failure contracts.

## Example 1: unexplained positional flags

**Circumstance:** Creating a user record includes a welcome-message preference,
administrator status and session limit. This example only builds the record.

**Bad:** A reader must look up the meanings of `True`, `False` and `3`.
**Good:** The call states those meanings.

```python
def user_record(name, send_welcome, is_admin, session_limit):
    return {
        "name": name,
        "send_welcome": send_welcome,
        "is_admin": is_admin,
        "session_limit": session_limit,
    }


opaque_call = user_record("Ada", True, False, 3)
explicit_call = user_record("Ada", send_welcome=True, is_admin=False, session_limit=3)
assert opaque_call == explicit_call
assert explicit_call["is_admin"] is False
```

A keyword-only interface can require the clearer form. Similarly,
`timeout_seconds=5` communicates more than an unexplained `timeout=5000`.

## Example 2: an empty result disguises a failed operation

**Circumstance:** A directory reader returns a list on success. Unavailability
must be distinguishable from a directory containing no entries.

**Bad:** Swallow every exception and return an empty list. **Good:** Preserve
the failure unless this boundary owns a documented recovery or translation.

```python
def unavailable_directory():
    raise ConnectionError("Directory unavailable")


def bad_list_entries(read_entries):
    try:
        return read_entries()
    except Exception:
        return []


assert bad_list_entries(unavailable_directory) == []  # Looks like success.

try:
    unavailable_directory()
except ConnectionError as error:
    assert str(error) == "Directory unavailable"
else:
    raise AssertionError("Unavailability must remain observable")
```

Returning an explicitly labelled cached result could be a valid alternative
under an agreed availability requirement. Silently converting failure into
successful emptiness changes the meaning of the result.

**Review question:** What must a reader guess here, and can an error be mistaken
for a successful result?

## References

Tim Peters, [The Zen of Python](https://peps.python.org/pep-0020/).
