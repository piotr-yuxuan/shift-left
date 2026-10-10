# Clear resource ownership and limited lifetimes

[All programming principles](../SKILL.md)

**Definition:** Assign each acquired resource an identifiable owner responsible
for release on normal completion and failure. Acquire it when needed and release
it when the dependent operation ends. A lock or transaction must cover the whole
invariant it protects, while excluding unrelated work that unnecessarily extends
its lifetime.

Make acquisition and release explicit. Do not hold database transactions or
locks across unrelated network I/O, retry delays or user interaction. Retaining
a checked-out database connection across these operations requires a concrete
requirement and documented resource budget.

## Example 1: failure before manual cleanup

**Circumstance:** Reading a stream succeeds, but converting its contents to an
integer fails. A stream is used so the example needs no external file.

**Bad:** Cleanup after the conversion is skipped on failure. **Good:** A context
manager owns cleanup when the body exits.

```python
from io import StringIO

bad_stream = StringIO("not an integer")
try:
    int(bad_stream.read())
    bad_stream.close()
except ValueError:
    pass
assert not bad_stream.closed
bad_stream.close()  # Clean up the deliberately bad demonstration.

good_stream = StringIO("not an integer")
try:
    with good_stream:
        int(good_stream.read())
except ValueError:
    pass
assert good_stream.closed
```

This example checks release on failure. A particular resource's context-manager
contract must be understood: leaving a transaction and closing a connection are
distinct operations, and different APIs assign them differently.

## Example 2: reducing lock time without breaking atomicity

**Circumstance:** A transfer updates two in-memory balances under one shared
lock. Formatting its input description does not depend on those balances.

```text
Bad: hold the lock during unrelated work.
  acquire lock
  format the input description
  check source balance, debit source and credit destination
  release lock

Good: keep the protected invariant together.
  format the input description
  acquire lock
  check source balance, debit source and credit destination
  release lock

Bad attempt to shorten the lock further:
  check source balance before acquiring the lock
  acquire lock, debit and credit, release lock
  Another transfer can spend that balance between the check and the debit.
```

The good boundary makes the check and both updates one protected operation.
It assumes every access requiring that invariant follows the same locking
protocol; a process-local lock does not coordinate separate processes.
The lock provides mutual exclusion, but does not undo a debit if the following
credit fails. Failure atomicity requires its own mechanism, such as a database
transaction that commits both changes or rolls both back.

**Review question:** Who releases the resource if this operation fails, and
which exact invariant determines the necessary lifetime?

## References

[C++ Core Guidelines: resource management](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#S-resource)
and [minimising critical sections](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#Rconc-time);
Python's [context management documentation](https://docs.python.org/3/library/contextlib.html).
