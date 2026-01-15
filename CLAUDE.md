# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Docling is a document processing SDK and CLI for parsing PDF, DOCX, HTML, and more into a unified document representation (DoclingDocument). It supports advanced PDF understanding including layout analysis, table structure recognition, OCR, and VLM integration.

## Development Commands

```bash
# Environment setup
uv sync                          # Create venv and install dependencies
uv venv --python 3.12 && uv sync # Use specific Python version

# Code quality
pre-commit install               # Install git hooks (required before committing)
pre-commit run --all-files       # Run linting/formatting manually
uv run mypy docling              # Type checking

# Testing
uv run pytest                              # Run all tests
uv run pytest tests/test_xxx.py            # Run single test file
uv run pytest tests/test_xxx.py::test_func # Run single test function
uv run pytest -x                           # Stop on first failure
DOCLING_GEN_TEST_DATA=1 uv run pytest      # Regenerate reference test data

# Documentation
mkdocs serve                     # Local docs server at http://localhost:8000

# CLI usage
docling <file_or_url>            # Convert document
docling --pipeline vlm --vlm-model granite_docling <file>  # Use VLM pipeline
```

## Architecture

### Core Processing Flow

```
InputDocument → Backend → Pipeline → ConversionResult → DoclingDocument
```

1. **DocumentConverter** (`docling/document_converter.py`): Main entry point. Routes documents to appropriate backends and pipelines based on format.

2. **Backends** (`docling/backend/`): Format-specific parsers that extract raw content.
   - `AbstractDocumentBackend`: Base class for all backends
   - `DeclarativeDocumentBackend`: For formats that convert directly to DoclingDocument (DOCX, HTML, Markdown)
   - `PaginatedDocumentBackend`: For paginated formats (PDF, images)

3. **Pipelines** (`docling/pipeline/`): Processing workflows.
   - `SimplePipeline`: Direct conversion for declarative backends
   - `StandardPdfPipeline`: Full PDF processing with layout/table/OCR models
   - `VlmPipeline`: Vision Language Model based processing
   - `AsrPipeline`: Audio speech recognition

4. **Models** (`docling/models/`): ML models for document understanding.
   - `stages/`: Processing stages (layout, OCR, table_structure, reading_order, etc.)
   - `factories/`: Model instantiation factories
   - `vlm_pipeline_models/`: VLM integrations

### Key Data Models (`docling/datamodel/`)

- `InputDocument`, `ConversionResult`: Input/output wrappers
- `PipelineOptions`, `PdfPipelineOptions`: Configuration classes
- `base_models.py`: Core types (InputFormat, ConversionStatus, Page)

### Plugin System

Entry point `docling_defaults` in `docling/models/plugins/defaults.py` registers default model implementations.

## Code Style

- **Formatter/Linter**: Ruff (configured in pyproject.toml)
- **Type Checker**: MyPy with Pydantic plugin
- **Python**: 3.9+ compatible, target 3.10 for mypy
