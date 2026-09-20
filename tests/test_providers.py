from unittest.mock import patch

import pytest

from phonexi import providers
from phonexi.providers import (
    CATALOG,
    GEMINI,
    GROQ,
    Selection,
    available_models,
    default_selection,
    find,
    key_order,
    selection_for,
)


def _env(tmp_path, text):
    p = tmp_path / ".env"
    p.write_text(text, encoding="utf-8")
    return p


# ── key_order: the key written highest in .env wins ─────────────────────────

def test_key_order_follows_the_file_top_to_bottom(tmp_path):
    env = _env(tmp_path, "GEMINI_API_KEY=g\nGROQ_API_KEY=q\n")
    with patch.dict("os.environ", {}, clear=True):
        assert key_order(env) == [GEMINI, GROQ]


def test_key_order_groq_first_when_written_first(tmp_path):
    env = _env(tmp_path, "GROQ_API_KEY=q\nOTHER=1\nGEMINI_API_KEY=g\n")
    with patch.dict("os.environ", {}, clear=True):
        assert key_order(env) == [GROQ, GEMINI]


def test_key_order_skips_empty_keys(tmp_path):
    env = _env(tmp_path, "GEMINI_API_KEY=\nGROQ_API_KEY=q\n")
    with patch.dict("os.environ", {}, clear=True):
        assert key_order(env) == [GROQ]


def test_key_order_appends_keys_only_in_the_environment(tmp_path):
    env = _env(tmp_path, "GEMINI_API_KEY=g\n")
    with patch.dict("os.environ", {"GROQ_API_KEY": "q"}, clear=True):
        assert key_order(env) == [GEMINI, GROQ]


def test_key_order_without_env_file(tmp_path):
    with patch.dict("os.environ", {}, clear=True):
        assert key_order(tmp_path / "missing.env") == []


# ── catalog ──────────────────────────────────────────────────────────────────

def test_catalog_has_both_providers():
    assert {m.provider for m in CATALOG} == {GROQ, GEMINI}


def test_available_models_only_lists_providers_with_a_key():
    models = available_models([GEMINI])
    assert models
    assert all(m.provider == GEMINI for m in models)


def test_available_models_keeps_key_order():
    models = available_models([GEMINI, GROQ])
    assert models[0].provider == GEMINI
    assert models[-1].provider == GROQ


def test_find_known_and_unknown():
    assert find("gemini-3.8-flash").provider == GEMINI
    assert find("no-such-model") is None


# ── selections ───────────────────────────────────────────────────────────────

def test_default_selection_gemini_when_its_key_is_on_top():
    sel = default_selection([GEMINI, GROQ])
    assert sel.provider == GEMINI


def test_default_selection_groq_when_its_key_is_on_top():
    sel = default_selection([GROQ, GEMINI])
    assert sel.provider == GROQ


def test_default_selection_falls_back_to_groq_without_keys():
    assert default_selection([]).provider == GROQ


def test_vision_model_is_used_for_both_modes():
    sel = selection_for(find("gemini-3.8-flash"))
    assert sel == Selection(GEMINI, "gemini-3.8-flash", "gemini-3.8-flash")


def test_text_only_model_keeps_the_env_vision_model():
    with patch("phonexi.providers.GROQ_MODEL_VISION", "qwen/qwen3.6-27b"):
        sel = selection_for(find("openai/gpt-oss-120b"))
    assert sel.text_model == "openai/gpt-oss-120b"
    assert sel.vision_model == "qwen/qwen3.6-27b"


def test_activate_changes_the_active_selection():
    before = providers.active()
    try:
        providers.activate(Selection(GEMINI, "a", "b"))
        assert providers.active() == Selection(GEMINI, "a", "b")
    finally:
        providers.activate(before)


def test_retired_gemini_2_5_flash_is_not_offered():
    # Listed by the models endpoint but answers 404 on this account.
    assert find("gemini-2.5-flash") is None


def test_fallback_skips_the_busy_model():
    from phonexi.providers import fallback_for
    assert fallback_for("gemini-3.5-flash") == "gemini-3.8-flash"
    assert fallback_for("gemini-3.8-flash") == "gemini-3.1-flash-lite"


def test_fallback_for_unknown_model_uses_the_first():
    from phonexi.providers import fallback_for
    assert fallback_for("gemini-custom") == "gemini-3.8-flash"
