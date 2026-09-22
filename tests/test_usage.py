from apiwells.probes.usage import (
    UsageObservation,
    extract_usage,
)


def test_complete_usage_is_normalized():
    result = extract_usage(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
        }
    )

    assert result == UsageObservation(
        available=True,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )

    assert result.complete is True


def test_missing_usage_is_unavailable():
    result = extract_usage(
        {
            "choices": []
        }
    )

    assert result.available is False
    assert result.complete is False

    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.total_tokens is None


def test_empty_usage_is_unavailable():
    result = extract_usage(
        {
            "usage": {}
        }
    )

    assert result.available is False
    assert result.complete is False


def test_partial_usage_is_available_but_incomplete():
    result = extract_usage(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }
        }
    )

    assert result.available is True
    assert result.complete is False

    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens is None


def test_total_tokens_is_not_estimated():
    result = extract_usage(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }
        }
    )

    assert result.total_tokens is None


def test_invalid_token_values_are_ignored():
    result = extract_usage(
        {
            "usage": {
                "prompt_tokens": -1,
                "completion_tokens": "5",
                "total_tokens": True,
            }
        }
    )

    assert result.available is False
    assert result.complete is False

    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.total_tokens is None


def test_partial_valid_usage_ignores_invalid_fields():
    result = extract_usage(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": "invalid",
                "total_tokens": 15,
            }
        }
    )

    assert result.available is True
    assert result.complete is False

    assert result.prompt_tokens == 10
    assert result.completion_tokens is None
    assert result.total_tokens == 15


def test_extra_provider_usage_fields_do_not_break_extraction():
    result = extract_usage(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "reasoning_tokens": 3,
                "cached_tokens": 4,
            }
        }
    )

    assert result.complete is True

    assert result.as_metrics() == {
        "usage_available": True,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_non_dict_payload_is_unavailable():
    result = extract_usage(
        [
            {
                "usage": {
                    "total_tokens": 15
                }
            }
        ]
    )

    assert result.available is False