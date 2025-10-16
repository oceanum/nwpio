# GitHub Actions Workflows

This directory contains GitHub Actions workflows for CI/CD.

## Workflows

### CI (`ci.yml`)

**Trigger**: On every push to `main` and all pull requests

**Jobs**:
1. **Test** - Run tests on multiple Python versions (3.9-3.12) and platforms (Ubuntu, macOS, Windows)
   - Installs system dependencies (eccodes)
   - Runs pytest with coverage
   - Uploads coverage to Codecov

2. **Lint** - Code quality checks
   - Runs ruff for linting
   - Checks code formatting with black
   - Runs mypy for type checking

3. **Build** - Build and validate package
   - Builds source and wheel distributions
   - Validates package with twine
   - Uploads build artifacts

### Publish (`publish.yml`)

**Trigger**: On GitHub release publication

**Jobs**:
1. **Test** - Run full test suite before publishing
2. **Build** - Build distribution packages
3. **Publish** - Publish to PyPI using trusted publishing

**Requirements**:
- Configure PyPI trusted publishing in your PyPI account settings
- Add `pypi` environment in GitHub repository settings
- No API tokens needed - uses OIDC trusted publishing

## Setting Up PyPI Trusted Publishing

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new publisher:
   - **PyPI Project Name**: `nwpio`
   - **Owner**: `oceanum`
   - **Repository name**: `nwpio`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`

3. In GitHub repository settings:
   - Go to Settings → Environments
   - Create environment named `pypi`
   - (Optional) Add protection rules for deployment approval

## Creating a Release

To publish a new version to PyPI:

1. Update version in `pyproject.toml`
2. Commit and push changes
3. Create a new release on GitHub:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
4. Go to GitHub → Releases → Draft a new release
5. Choose the tag, add release notes
6. Publish the release
7. The workflow will automatically build and publish to PyPI

## Local Testing

Test the workflows locally before pushing:

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest -v tests/

# Run linting
ruff check .
black --check .

# Build package
python -m build
twine check dist/*
```
