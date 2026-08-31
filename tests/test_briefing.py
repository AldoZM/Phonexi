import pytest

from phonexi.briefing import MAX_CHARS, BriefingError, load


def _write(tmp_path, name: str, text: str):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_load_returns_file_text(tmp_path):
    p = _write(tmp_path, "brief.md", "Vacante: backend Java con Kafka.")
    assert load(p) == "Vacante: backend Java con Kafka."


def test_load_strips_surrounding_whitespace(tmp_path):
    p = _write(tmp_path, "brief.txt", "\n\n  Spring Boot y Kafka  \n\n")
    assert load(p) == "Spring Boot y Kafka"


def test_load_accepts_txt_extension(tmp_path):
    p = _write(tmp_path, "brief.txt", "contenido")
    assert load(p) == "contenido"


def test_load_accepts_uppercase_extension(tmp_path):
    p = _write(tmp_path, "brief.MD", "contenido")
    assert load(p) == "contenido"


def test_load_rejects_unsupported_extension(tmp_path):
    p = _write(tmp_path, "brief.pdf", "contenido")
    with pytest.raises(BriefingError, match=r"\.md.*\.txt"):
        load(p)


def test_load_rejects_missing_file(tmp_path):
    with pytest.raises(BriefingError, match="not found"):
        load(tmp_path / "no_existe.md")


def test_load_rejects_directory(tmp_path):
    d = tmp_path / "carpeta.md"
    d.mkdir()
    with pytest.raises(BriefingError, match="not a file"):
        load(d)


def test_load_rejects_empty_file(tmp_path):
    p = _write(tmp_path, "brief.md", "")
    with pytest.raises(BriefingError, match="empty"):
        load(p)


def test_load_rejects_whitespace_only_file(tmp_path):
    p = _write(tmp_path, "brief.md", "   \n\t\n  ")
    with pytest.raises(BriefingError, match="empty"):
        load(p)


def test_load_rejects_file_over_max_chars(tmp_path):
    p = _write(tmp_path, "brief.md", "x" * (MAX_CHARS + 1))
    with pytest.raises(BriefingError, match="too large"):
        load(p)


def test_load_accepts_file_at_max_chars(tmp_path):
    p = _write(tmp_path, "brief.md", "x" * MAX_CHARS)
    assert len(load(p)) == MAX_CHARS


def test_load_rejects_non_utf8_file(tmp_path):
    p = tmp_path / "brief.md"
    p.write_bytes(b"\xff\xfe\x00binario")
    with pytest.raises(BriefingError, match="UTF-8"):
        load(p)


def test_error_message_names_the_path(tmp_path):
    missing = tmp_path / "no_existe.md"
    with pytest.raises(BriefingError, match="no_existe.md"):
        load(missing)
