"""Tests for notebook view conversion."""

import json

import pytest

from graderbot.notebook_view import (
    extract_output_text,
    format_notebook_for_prompt,
    get_cell_excerpt,
    parse_notebook,
    truncate_text,
)


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_short_text_unchanged(self):
        """Test that short text is not modified."""
        text = "Hello, world!"
        assert truncate_text(text, 100) == text

    def test_long_text_truncated(self):
        """Test that long text is truncated."""
        text = "x" * 100
        result = truncate_text(text, 50)
        assert len(result) <= 50
        assert "[truncated]" in result

    def test_exact_length(self):
        """Test text at exact max length."""
        text = "x" * 50
        assert truncate_text(text, 50) == text


class TestExtractOutputText:
    """Tests for extract_output_text function."""

    def test_stream_output(self):
        """Test extracting stream output."""
        output = {"output_type": "stream", "text": "Hello\n"}
        assert extract_output_text(output) == "Hello\n"

    def test_execute_result(self):
        """Test extracting execute_result."""
        output = {
            "output_type": "execute_result",
            "data": {"text/plain": "42"},
        }
        assert extract_output_text(output) == "42"

    def test_display_data_html(self):
        """Test extracting display_data with HTML."""
        output = {
            "output_type": "display_data",
            "data": {"text/html": "<div>content</div>"},
        }
        assert extract_output_text(output) == "[HTML output]"

    def test_image_output(self):
        """Test extracting image output."""
        output = {
            "output_type": "display_data",
            "data": {"image/png": "base64data"},
        }
        assert extract_output_text(output) == "[Image output]"

    def test_error_output(self):
        """Test extracting error output."""
        output = {
            "output_type": "error",
            "ename": "ValueError",
            "evalue": "invalid input",
        }
        result = extract_output_text(output)
        assert "ValueError" in result
        assert "invalid input" in result


class TestParseNotebook:
    """Tests for parse_notebook function."""

    def test_parse_simple_notebook(self):
        """Test parsing a simple notebook."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": "# Title",
                    "metadata": {},
                },
                {
                    "cell_type": "code",
                    "source": "x = 42",
                    "metadata": {},
                    "execution_count": 1,
                    "outputs": [
                        {"output_type": "execute_result", "data": {"text/plain": "42"}}
                    ],
                },
            ],
        }

        view = parse_notebook(notebook)

        assert len(view.cells) == 2
        assert view.cells[0].cell_type == "markdown"
        assert view.cells[0].source == "# Title"
        assert view.cells[1].cell_type == "code"
        assert view.cells[1].execution_count == 1
        assert "42" in view.cells[1].outputs[0]

    def test_parse_notebook_json_string(self):
        """Test parsing notebook from JSON string."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "source": "print('hello')",
                    "metadata": {},
                    "execution_count": None,
                    "outputs": [],
                },
            ],
        }

        view = parse_notebook(json.dumps(notebook))

        assert len(view.cells) == 1
        assert view.cells[0].execution_count is None

    def test_cell_indices(self):
        """Test that cell indices are correct."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {"cell_type": "code", "source": "a", "metadata": {}, "outputs": []},
                {"cell_type": "code", "source": "b", "metadata": {}, "outputs": []},
                {"cell_type": "code", "source": "c", "metadata": {}, "outputs": []},
            ],
        }

        view = parse_notebook(notebook)

        assert view.cells[0].index == 0
        assert view.cells[1].index == 1
        assert view.cells[2].index == 2


class TestFormatNotebookForPrompt:
    """Tests for format_notebook_for_prompt function."""

    def test_format_includes_cells(self):
        """Test that formatted output includes cell content."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "source": "x = 42",
                    "metadata": {},
                    "execution_count": 1,
                    "outputs": [],
                },
            ],
        }

        view = parse_notebook(notebook)
        formatted = format_notebook_for_prompt(view)

        assert "[Cell 0]" in formatted
        assert "(code)" in formatted
        assert "x = 42" in formatted

    def test_exclude_markdown(self):
        """Test excluding markdown cells."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {"cell_type": "markdown", "source": "# Title", "metadata": {}},
                {
                    "cell_type": "code",
                    "source": "code",
                    "metadata": {},
                    "outputs": [],
                },
            ],
        }

        view = parse_notebook(notebook)
        formatted = format_notebook_for_prompt(view, include_markdown=False)

        assert "# Title" not in formatted
        assert "code" in formatted


class TestGetCellExcerpt:
    """Tests for get_cell_excerpt function."""

    def test_get_excerpt(self):
        """Test getting a cell excerpt."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "source": "x = 42",
                    "metadata": {},
                    "outputs": [],
                },
            ],
        }

        view = parse_notebook(notebook)
        excerpt = get_cell_excerpt(view, 0)

        assert "x = 42" in excerpt

    def test_invalid_index(self):
        """Test getting excerpt for invalid index."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [],
        }

        view = parse_notebook(notebook)
        assert get_cell_excerpt(view, 0) == ""
        assert get_cell_excerpt(view, -1) == ""
