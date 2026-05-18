"""OAuth state signing — bound to (user, platform), 10-min TTL."""
from social.oauth import sign_state, verify_state


def test_state_round_trips():
    state = sign_state(7, "linkedin_page")
    assert verify_state(state, 7, "linkedin_page")


def test_state_rejects_different_user():
    state = sign_state(7, "linkedin_page")
    assert not verify_state(state, 8, "linkedin_page")


def test_state_rejects_different_platform():
    state = sign_state(7, "linkedin_page")
    assert not verify_state(state, 7, "meta")


def test_state_rejects_garbage():
    assert not verify_state("not-a-state", 7, "linkedin_page")


def test_state_rejects_expired(monkeypatch):
    from social import oauth as oauth_module

    state = sign_state(7, "linkedin_page")
    # Force the max-age to zero so even a freshly-minted state has expired.
    monkeypatch.setattr(oauth_module, "_STATE_MAX_AGE_S", -1)
    assert not verify_state(state, 7, "linkedin_page")
