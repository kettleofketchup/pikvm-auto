"""Tests for config module."""

from __future__ import annotations

from unittest.mock import patch

from pikvm_auto._internal.config import PiKVMSettings


def test_settings_from_env(monkeypatch) -> None:
    """Settings load from PIKVM_ env vars."""
    monkeypatch.setenv("PIKVM_HOST", "192.168.1.100")
    monkeypatch.setenv("PIKVM_USER", "admin")
    monkeypatch.setenv("PIKVM_PASSWORD", "secret")
    monkeypatch.delenv("PIKVM_SCHEMA", raising=False)
    monkeypatch.delenv("PIKVM_CERT_TRUSTED", raising=False)
    settings = PiKVMSettings()
    assert settings.host == "192.168.1.100"
    assert settings.user == "admin"
    assert settings.password == "secret"


def test_settings_defaults(monkeypatch) -> None:
    """Settings have sensible defaults."""
    monkeypatch.delenv("PIKVM_HOST", raising=False)
    monkeypatch.delenv("PIKVM_USER", raising=False)
    monkeypatch.delenv("PIKVM_PASSWORD", raising=False)
    monkeypatch.delenv("PIKVM_SCHEMA", raising=False)
    monkeypatch.delenv("PIKVM_CERT_TRUSTED", raising=False)
    settings = PiKVMSettings(host="10.0.0.1", password="pass")
    assert settings.user == "admin"
    assert settings.schema_ == "https"
    assert settings.cert_trusted is False


def test_settings_create_client(monkeypatch) -> None:
    """Settings can create a PiKVM client instance."""
    monkeypatch.delenv("PIKVM_HOST", raising=False)
    monkeypatch.delenv("PIKVM_USER", raising=False)
    monkeypatch.delenv("PIKVM_PASSWORD", raising=False)
    monkeypatch.delenv("PIKVM_SCHEMA", raising=False)
    monkeypatch.delenv("PIKVM_CERT_TRUSTED", raising=False)
    settings = PiKVMSettings(host="10.0.0.1", user="admin", password="pass")
    with patch("pikvm_auto._internal.config.PiKVM") as mock_pikvm:
        client = settings.create_client()
        assert client is not None
        mock_pikvm.assert_called_once_with(
            hostname="10.0.0.1",
            username="admin",
            password="pass",
            schema="https",
            cert_trusted=False,
        )
