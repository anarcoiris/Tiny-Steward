---
name: pytest
type: skill
requires: [pwsh, bash, python]
provides: [testing, test-execution]
tags: [python, pytest, test, testing, unit-test, assert]
related: [venv, pip]
---

# Pytest — Python Testing

Run and write Python tests.

## Run Tests

```bash
# Run all tests
pytest

# Verbose
pytest -v

# Specific file
pytest tests/test_module.py

# Specific test
pytest tests/test_module.py::test_function

# With output capture disabled
pytest -s

# Stop on first failure
pytest -x
```

## Write Tests

```python
# tests/test_example.py

def test_addition():
    assert 1 + 1 == 2

def test_string():
    assert "hello".upper() == "HELLO"

class TestClass:
    def test_method(self):
        assert [1, 2, 3] == [1, 2, 3]
```

## Errors

### ModuleNotFoundError in tests

Ensure the package is installed in development mode:

```bash
pip install -e .
```

Or add the project root to PYTHONPATH:

```bash
PYTHONPATH=. pytest
```

### No tests collected

- Files must be named `test_*.py` or `*_test.py`
- Functions must start with `test_`
- Check `pytest.ini` or `pyproject.toml` for `testpaths` configuration
