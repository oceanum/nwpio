# NWPIO Documentation

This directory contains the source files for the NWPIO documentation, built with MkDocs.

## Building the Documentation

### Install Dependencies

```bash
pip install -e ".[docs]"
```

### Build

```bash
mkdocs build
```

The built site will be in the `site/` directory.

### Serve Locally

```bash
mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser.

## Documentation Structure

```
docs/
├── index.md                    # Home page
├── getting-started/
│   ├── installation.md         # Installation guide
│   ├── quickstart.md          # Quick start guide
│   └── configuration.md       # Configuration guide
├── guide/
│   ├── downloading.md         # Downloading data
│   ├── processing.md          # Processing to Zarr
│   ├── workflow.md            # Complete workflow
│   └── data-sources.md        # Data sources
├── api/
│   ├── overview.md            # API overview
│   ├── config.md              # Configuration API
│   ├── downloader.md          # Downloader API
│   ├── processor.md           # Processor API
│   └── cli.md                 # CLI reference
├── advanced/
│   ├── formatting.md          # Output path formatting
│   ├── write-local-first.md   # Write local first feature
│   └── performance.md         # Performance tips
└── about/
    ├── changelog.md           # Changelog
    ├── contributing.md        # Contributing guide
    └── license.md             # License
```

## Contributing to Documentation

1. Edit the Markdown files in `docs/`
2. Test locally with `mkdocs serve`
3. Build with `mkdocs build` to check for errors
4. Submit a pull request

## Deploying

To deploy to GitHub Pages:

```bash
mkdocs gh-deploy
```

This will build the docs and push them to the `gh-pages` branch.
