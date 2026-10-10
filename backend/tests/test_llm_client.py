import pytest

from app.services.llm_client import LLMError, extract_json


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    text = '好的,以下是结果:\n```json\n{"picks": []}\n```\n希望有帮助'
    assert extract_json(text) == {"picks": []}


def test_extract_json_with_surrounding_text():
    assert extract_json('前缀 {"a": 1} 后缀') == {"a": 1}


def test_extract_invalid_json_raises():
    with pytest.raises(LLMError):
        extract_json("完全不是 JSON 的回答")
