"""Smoke tests for the Sentry integration wiring.

These don't actually contact Sentry — they just verify that the SDK is
initialised when SENTRY_DSN is set and not when it's empty.
"""

import importlib

import pytest


def test_sentry_disabled_when_dsn_unset(monkeypatch, settings):
    """No DSN = SDK never initialised. The settings import must not fail
    and SENTRY_DSN should resolve to the empty string."""
    # Already-loaded settings module: DSN is whatever the env decided. We
    # just assert that the attribute exists and that the SDK only ships
    # events when it was configured.
    import sentry_sdk

    if settings.SENTRY_DSN:
        # In CI we deliberately don't set the DSN, so this branch is the
        # "developer ran tests with real env" path. Don't break their
        # flow — just verify the client looks initialised.
        assert sentry_sdk.Hub.current.client is not None, (
            "SENTRY_DSN is set but Sentry SDK did not initialise."
        )
    else:
        # With no DSN, the SDK either has no client or its client has no
        # transport — either way, capture_message should be a no-op.
        # We use the public API to assert this without poking internals.
        result = sentry_sdk.capture_message("test-noop", level="warning")
        # Without a DSN, capture_message returns None.
        assert result is None or sentry_sdk.Hub.current.client is None, (
            "Sentry appears to be capturing events without a DSN configured."
        )


def test_scrubber_redacts_secret_shaped_headers():
    """The _scrub_event hook in settings.py should redact secret-shaped
    keys in request headers/cookies/data and extras."""
    from luma_support import settings as lsettings

    scrubber = getattr(lsettings, "_scrub_event", None)
    if scrubber is None:
        pytest.skip("Sentry not enabled in this environment (no DSN).")

    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer hunter2",
                "X-Csrf-Token": "abc",
                "User-Agent": "curl/8",
            },
            "cookies": {"sessionid": "xyz", "csrftoken": "qwe"},
            "data": {"password": "p@ss", "name": "marco"},
        },
        "extra": {
            "api_key": "sk-abc",
            "client_id": 17,
        },
    }
    out = scrubber(event, {})
    assert out["request"]["headers"]["Authorization"] == "[scrubbed]"
    assert out["request"]["headers"]["X-Csrf-Token"] == "[scrubbed]"
    assert out["request"]["headers"]["User-Agent"] == "curl/8"
    assert out["request"]["cookies"]["sessionid"] == "[scrubbed]"
    assert out["request"]["data"]["password"] == "[scrubbed]"
    assert out["request"]["data"]["name"] == "marco"
    assert out["extra"]["api_key"] == "[scrubbed]"
    assert out["extra"]["client_id"] == 17
