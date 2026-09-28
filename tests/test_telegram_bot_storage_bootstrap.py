from __future__ import annotations

import pytest

import telegram_bot.bot as bot_module


def test_persistence_disabled_does_not_call_init_db(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PERSIST_READINGS", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def _fail_if_called():
        raise AssertionError("init_db() must not be called when persistence is disabled")

    monkeypatch.setattr(bot_module, "init_db", _fail_if_called)

    bot_module.ensure_reading_storage_ready()


def test_persistence_enabled_calls_init_db_at_startup(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PERSIST_READINGS", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    calls = []
    monkeypatch.setattr(bot_module, "init_db", lambda: calls.append(1))

    bot_module.ensure_reading_storage_ready()

    assert calls == [1]


def test_init_db_failure_is_not_swallowed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PERSIST_READINGS", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    def _raise():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(bot_module, "init_db", _raise)

    with pytest.raises(RuntimeError, match="connection refused"):
        bot_module.ensure_reading_storage_ready()


def test_persistence_flag_without_database_url_does_not_call_init_db(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PERSIST_READINGS", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def _fail_if_called():
        raise AssertionError("init_db() must not be called without DATABASE_URL")

    monkeypatch.setattr(bot_module, "init_db", _fail_if_called)

    bot_module.ensure_reading_storage_ready()
