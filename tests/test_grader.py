"""Tests for the grader module."""

import json

import pytest

from graderbot.grader import (
    extract_json_from_response,
    parse_and_validate_response,
)
from graderbot.schema import Rating


class TestExtractJsonFromResponse:
    """Tests for extract_json_from_response function."""

    def test_raw_json(self):
        """Test extracting raw JSON."""
        content = '{"key": "value"}'
        assert extract_json_from_response(content) == '{"key": "value"}'

    def test_json_in_code_block(self):
        """Test extracting JSON from markdown code block."""
        content = '''Here is the result:

```json
{"key": "value"}
```

That's all.'''
        assert extract_json_from_response(content) == '{"key": "value"}'

    def test_json_in_plain_code_block(self):
        """Test extracting JSON from plain code block."""
        content = '''```
{"key": "value"}
```'''
        assert extract_json_from_response(content) == '{"key": "value"}'

    def test_json_with_surrounding_text(self):
        """Test extracting JSON with surrounding text."""
        content = '''Sure! Here's the grading:

{"schema_version": "1.0", "exercises": [], "overall_summary": "test"}

Let me know if you need changes.'''
        result = extract_json_from_response(content)
        parsed = json.loads(result)
        assert parsed["schema_version"] == "1.0"


class TestParseAndValidateResponse:
    """Tests for parse_and_validate_response function."""

    def test_valid_response(self):
        """Test parsing a valid response."""
        content = json.dumps({
            "schema_version": "1.0",
            "exercises": [
                {
                    "exercise_id": "Exercise 1",
                    "rating": "EXCELLENT",
                    "rationale": "Perfect solution.",
                    "evidence": [{"cell_index": 0, "excerpt": "code"}],
                    "missing_or_wrong": [],
                    "flags": [],
                }
            ],
            "overall_summary": "Great work!",
        })

        result = parse_and_validate_response(content)

        assert result.schema_version == "1.0"
        assert len(result.exercises) == 1
        assert result.exercises[0].rating == Rating.EXCELLENT

    def test_response_in_code_block(self):
        """Test parsing response wrapped in code block."""
        json_data = {
            "schema_version": "1.0",
            "exercises": [],
            "overall_summary": "Empty.",
        }
        content = f"```json\n{json.dumps(json_data)}\n```"

        result = parse_and_validate_response(content)
        assert result.overall_summary == "Empty."

    def test_invalid_json(self):
        """Test that invalid JSON raises error."""
        content = "not valid json"

        with pytest.raises(json.JSONDecodeError):
            parse_and_validate_response(content)

    def test_invalid_schema(self):
        """Test that invalid schema raises error."""
        content = json.dumps({
            "schema_version": "1.0",
            # Missing required fields
        })

        with pytest.raises(Exception):  # ValidationError
            parse_and_validate_response(content)

    def test_minimal_valid_response(self):
        """Test parsing minimal valid response."""
        content = json.dumps({
            "exercises": [
                {
                    "exercise_id": "Ex 1",
                    "rating": "OK",
                    "rationale": "Fine.",
                }
            ],
            "overall_summary": "Done.",
        })

        result = parse_and_validate_response(content)
        assert len(result.exercises) == 1
