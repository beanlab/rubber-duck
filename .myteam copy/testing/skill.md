---
name: Testing
description: |
  This skill describes our philosophy towards the kinds of tests we write
  and the framework used to implement tests.
  If you need to read, add, or modify tests, load this skill.
---

## Testing

### Philosophy

- tests should focus on public interface behavior rather than internal implementation details
- tests should prefer high-level use cases that run real application commands in an isolated environment
- assertions should focus on observable results such as exit status, output, and final filesystem state
- careful consideration should be given to what other states might emit the same assertions, and pick assertions that uniquely prove correct behavior
- private helper tests are secondary and should only be added when a behavior is hard to capture through the interface
- new behavior should be traced back to the interface contract in `governing_docs/application_interface.md`
- tests should act as evidence that the documented interface works as intended

### Process

Run tests with:

``` 
uv run pytest
```

Tests are found in `tests/`.

The full test suite takes about 30 seconds to run. Plan accordingly. 