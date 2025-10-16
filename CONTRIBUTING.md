# Contributing to NWPIO

Thank you for your interest in contributing to NWPIO! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- eccodes library (for GRIB support)
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone git@github.com:oceanum/nwpio.git
   cd nwpio
   ```

2. **Install system dependencies**:

   **Ubuntu/Debian**:
   ```bash
   sudo apt-get install libeccodes-dev
   ```

   **macOS**:
   ```bash
   brew install eccodes
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install in development mode**:
   ```bash
   pip install -e ".[dev,docs]"
   ```

## Development Workflow

### Running Tests

Run the full test suite:
```bash
pytest -v tests/
```

Run with coverage:
```bash
pytest -v --cov=nwpio --cov-report=term-missing tests/
```

Run specific test file:
```bash
pytest tests/test_config.py -v
```

### Code Quality

**Linting with ruff**:
```bash
ruff check .
```

**Auto-fix issues**:
```bash
ruff check --fix .
```

**Format code with black**:
```bash
black .
```

**Type checking with mypy**:
```bash
mypy nwpio --ignore-missing-imports
```

### Building Documentation

Build the documentation:
```bash
mkdocs build
```

Serve locally:
```bash
mkdocs serve
```

Then open http://127.0.0.1:8000

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Follow conventional commits format:

- `feat: add new feature`
- `fix: resolve bug in downloader`
- `docs: update installation guide`
- `test: add tests for processor`
- `refactor: simplify config validation`
- `chore: update dependencies`

### Pull Request Process

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** and commit:
   ```bash
   git add .
   git commit -m "feat: add my new feature"
   ```

3. **Run tests and linting**:
   ```bash
   pytest -v tests/
   ruff check .
   black --check .
   ```

4. **Push to GitHub**:
   ```bash
   git push origin feature/my-new-feature
   ```

5. **Create a Pull Request** on GitHub

6. **Wait for CI checks** to pass

7. **Address review comments** if any

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Maximum line length: 88 characters (black default)
- Use descriptive variable and function names
- Add docstrings to all public functions and classes

### Docstring Format

Use Google-style docstrings:

```python
def download_grib(
    product: str,
    cycle: datetime,
    max_lead_time: int,
) -> list[str]:
    """Download GRIB files from cloud archive.

    Args:
        product: NWP product name (e.g., 'gfs', 'ecmwf-hres')
        cycle: Forecast initialization time
        max_lead_time: Maximum lead time in hours

    Returns:
        List of downloaded file paths

    Raises:
        ValueError: If product is not supported
        RuntimeError: If download fails
    """
    pass
```

## Testing Guidelines

- Write tests for all new features
- Maintain or improve code coverage
- Use descriptive test names: `test_download_config_validates_cycle`
- Use fixtures for common test setup
- Mock external dependencies (GCS, network calls)

## Releasing

Releases are handled automatically via GitHub Actions when a new release is published.

### Version Numbering

Follow semantic versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Process

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG** (if exists)
3. **Commit changes**:
   ```bash
   git commit -am "chore: bump version to 0.2.0"
   git push
   ```
4. **Create and push tag**:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
5. **Create GitHub Release**:
   - Go to GitHub → Releases → Draft a new release
   - Choose the tag
   - Add release notes
   - Publish release
6. **GitHub Actions** will automatically publish to PyPI

## Getting Help

- **Issues**: Open an issue on GitHub for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Email**: developers@oceanum.science

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## License

By contributing to NWPIO, you agree that your contributions will be licensed under the MIT License.
