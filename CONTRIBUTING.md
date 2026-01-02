# Contributing to the Fabric Ontology Importer

First off, thanks for taking the time to contribute! This project aims to make it easy to import RDF/TTL and DTDL ontologies into Microsoft Fabric, so every improvement helps the community.

## 📋 Ground Rules

- Be respectful and follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Discuss big changes in an issue before submitting a PR.
- Keep pull requests focused and easy to review.
- Add or update tests when fixing bugs or implementing features.
- Document user-facing changes in the README and/or CHANGELOG.

## 🧱 Project Structure

```
src/
  cli/            # Command-line interface orchestration
  converters/     # Shared conversion utilities and helpers
  dtdl/           # DTDL parser and converter
  models/         # Shared Fabric ontology data classes
  ...             # Additional modules (fabric client, validation, etc.)
review/           # Architecture and standards review documents
samples/          # Example RDF, DTDL, and CSV datasets
```

## 🛠️ Development Workflow

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/my-enhancement
   ```
2. **Install dependencies** (Python 3.9+ recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```
3. **Run tests** before committing:
   ```bash
   pytest
   ```
4. **Format & lint** (optional but appreciated):
   ```bash
   ruff check src tests
   ruff format src tests
   ```
5. **Commit** using conventional messages when possible:
   ```bash
   feat: add custom DTDL validator
   fix: handle xsd:duration mapping
   docs: update configuration guide
   ```
6. **Push** to your fork and open a pull request against `main`.

## 📝 Docstring Style Guide

This project uses **Google-style docstrings** for all Python code. All public modules, classes, methods, and functions should have docstrings.

### Module Docstrings

```python
"""Short one-line summary of module purpose.

Longer description providing more context about the module's functionality,
architecture, and key components. Can include multiple paragraphs.

Example:
    from mymodule import MyClass
    
    obj = MyClass()
    result = obj.do_something()
"""
```

### Function/Method Docstrings

```python
def my_function(param1: str, param2: int = 10) -> bool:
    """Short one-line summary of function.
    
    More detailed description explaining what the function does,
    any important behavior, and usage notes.
    
    Args:
        param1: Description of param1. Should be concise but clear.
        param2: Description of param2 with default value context.
            Can use indentation for multi-line descriptions.
    
    Returns:
        Description of the return value and its meaning.
        Can span multiple lines if needed.
    
    Raises:
        ValueError: When param1 is empty or invalid.
        TypeError: When param2 is not an integer.
    
    Example:
        >>> result = my_function("test", 20)
        >>> print(result)
        True
    
    Note:
        Any additional notes, warnings, or important context.
    """
    pass
```

### Class Docstrings

```python
class MyClass:
    """Short one-line summary of class purpose.
    
    Longer description of the class, its responsibilities,
    and how it fits into the system architecture.
    
    Attributes:
        attribute1: Description of public attribute1.
        attribute2: Description of public attribute2.
    
    Example:
        >>> obj = MyClass()
        >>> obj.do_something()
    """
    
    def __init__(self, param1: str):
        """Initialize MyClass.
        
        Args:
            param1: Description of initialization parameter.
        """
        self.attribute1 = param1
```

### Key Guidelines

- **Always include docstrings** for public modules, classes, and functions
- **Use present tense**: "Returns the result" not "Return the result"
- **Be concise but clear**: First line should be a short summary
- **Type hints in code**: Don't repeat type information from annotations in docstrings
- **Examples help**: Include usage examples for complex APIs
- **Document exceptions**: List all exceptions that callers should handle

### Section Order

1. Short summary (one line)
2. Extended description (optional)
3. Args (for functions/methods)
4. Returns (for functions/methods)
5. Raises (if applicable)
6. Yields (for generators)
7. Example (if helpful)
8. Note/Warning (if applicable)


## ✅ Pull Request Checklist

- [ ] Tests pass locally (`pytest`).
- [ ] New/updated code is covered by tests.
- [ ] Documentation reflects the change.
- [ ] CHANGELOG has an entry under "Unreleased".
- [ ] Linked related issues in the PR description.

## 🧪 Testing Matrix

- **Unit tests** (`tests/test_*.py`).
- **Integration tests** (uploading sample ontologies to Fabric via mocked client).
- **Manual tests** (`samples/` contains real ontologies you can run through the CLI).

## 💬 Getting Help

- File an issue with as much detail as possible.
- Join the discussion in GitHub Discussions (coming soon).
- For security issues, follow the instructions in [SECURITY.md](SECURITY.md).

Happy contributing! 💙
