import json

from documind_ai.suggestions import suggest_fields


def test_suggestions_require_printed_value_and_quote(monkeypatch):
    import documind_ai.suggestions as module

    payload = {
        "suggestions": [
            {
                "field": "total",
                "raw_value": "INR 100.00",
                "page_number": 1,
                "quote": "Total: INR 100.00",
            },
            {
                "field": "vendor_name",
                "raw_value": "Invented Vendor",
                "page_number": 1,
                "quote": "Invented Vendor",
            },
            {
                "field": "total",
                "raw_value": "INR 999.00",
                "page_number": 1,
                "quote": "Total: INR 100.00",
            },
            {
                "field": "bank_account",
                "raw_value": "123",
                "page_number": 1,
                "quote": "Total: INR 100.00",
            },
        ]
    }
    monkeypatch.setattr(
        module, "ollama", lambda *args, **kwargs: {"message": {"content": json.dumps(payload)}}
    )
    assert suggest_fields([{"page_number": 1, "text": "Total: INR 100.00"}]) == [
        {"field": "total", "value": "100.00", "page_number": 1, "quote": "Total: INR 100.00"}
    ]
