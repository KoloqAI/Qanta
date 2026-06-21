from __future__ import annotations

from app.modules.auth.secrets import redact_for_client, mask_connection_value


class TestRedactForClient:
    """M1 gate: no secret appears in any client response."""

    def test_strips_secret_key(self):
        data = {"secret_key": "my-secret", "name": "safe"}
        result = redact_for_client(data)
        assert "secret_key" not in result
        assert result["name"] == "safe"

    def test_strips_broker_keys(self):
        data = {
            "ibkr_host": "127.0.0.1",
            "ibkr_port": 4002,
            "ibkr_client_id": 1,
            "name": "visible",
        }
        result = redact_for_client(data)
        assert "ibkr_host" not in result
        assert "ibkr_port" not in result
        assert result["name"] == "visible"

    def test_masks_key_like_fields(self):
        data = {"api_key": "sk-1234567890", "label": "hello"}
        result = redact_for_client(data)
        assert result["api_key"] == "***"
        assert result["label"] == "hello"

    def test_recursive_redaction(self):
        data = {
            "config": {
                "secret_key": "should-be-gone",
                "display": "visible",
            }
        }
        result = redact_for_client(data)
        assert "secret_key" not in result["config"]
        assert result["config"]["display"] == "visible"

    def test_empty_key_shows_empty(self):
        data = {"api_key": ""}
        result = redact_for_client(data)
        assert result["api_key"] == ""

    def test_no_secret_fields_passes_through(self):
        data = {"equity": 50000, "status": "active"}
        result = redact_for_client(data)
        assert result == data


class TestMaskConnectionValue:
    def test_masks_long_value(self):
        assert mask_connection_value("sk-1234567890abcdef") == "***cdef"

    def test_masks_short_value(self):
        assert mask_connection_value("ab") == "****"

    def test_masks_empty(self):
        assert mask_connection_value("") == "****"
