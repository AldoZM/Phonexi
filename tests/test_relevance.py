import pytest

from phonexi.relevance import select

SEP = "=" * 60

FICHA = "\n".join([
    SEP,
    "FICHA DE REFERENCIA - PERSONA",
    "Rol objetivo: backend",
    SEP,
    "",
    "COMO USAR ESTA FICHA",
    "Responde exactamente la pregunta que te hacen.",
    "",
    SEP,
    "1. PERFIL Y PITCH",
    SEP,
    "",
    "Ingeniero en computacion con experiencia en backend.",
    "",
    SEP,
    "2. CONSUMER LAG",
    SEP,
    "",
    "El lag es la diferencia entre el ultimo offset y el confirmado.",
    "",
    SEP,
    "3. INDICES EN MYSQL",
    SEP,
    "",
    "Un covering index cubre todas las columnas del select.",
    "",
    SEP,
    "4. STACK",
    SEP,
    "",
    "Java, Spring Boot, MySQL.",
])


def test_keeps_only_the_section_that_matches_the_question():
    out = select(FICHA, "como mides el consumer lag?")
    assert "2. CONSUMER LAG" in out
    assert "3. INDICES EN MYSQL" not in out


def test_keeps_the_preamble_rules_whatever_the_question():
    out = select(FICHA, "como mides el consumer lag?")
    assert "COMO USAR ESTA FICHA" in out
    assert "Responde exactamente la pregunta que te hacen." in out


def test_matches_ignoring_accents_and_case():
    out = select(FICHA, "Que son los INDICES en MySQL?")
    assert "3. INDICES EN MYSQL" in out


def test_returns_selected_sections_in_document_order():
    out = select(FICHA, "hablame del stack y del perfil")
    assert out.index("1. PERFIL Y PITCH") < out.index("4. STACK")


def test_respects_the_character_budget():
    out = select(FICHA, "lag offset index covering mysql stack perfil", max_chars=650)
    assert len(out) <= 650
    assert "4. STACK" not in out


def test_falls_back_to_document_order_when_nothing_matches():
    out = select(FICHA, "zzz?", max_chars=650)
    assert "1. PERFIL Y PITCH" in out


def test_returns_the_briefing_unchanged_when_it_has_no_sections():
    plain = "Vacante de backend Java con Kafka. Entrevista en espanol."
    assert select(plain, "cuentame de ti") == plain


def test_common_words_in_the_question_do_not_drive_the_selection():
    out = select(FICHA, "que es un covering index?")
    assert "3. INDICES EN MYSQL" in out
    assert "2. CONSUMER LAG" not in out


def test_rejects_a_non_positive_budget():
    with pytest.raises(ValueError):
        select(FICHA, "consumer lag", max_chars=0)


def test_keeps_an_unnumbered_banner_and_its_rules_in_the_preamble():
    ficha = "\n".join([
        SEP, "FICHA DE REFERENCIA", SEP, "",
        "COMO USAR ESTA FICHA", "No sustituyas el tema preguntado.", "",
        SEP, "1. CONSUMER LAG", SEP, "",
        "El lag es la diferencia entre offsets.", "",
        SEP, "2. INDICES", SEP, "",
        "Un covering index cubre las columnas del select.",
    ])
    out = select(ficha, "como mides el consumer lag?")
    assert "No sustituyas el tema preguntado." in out
    assert "2. INDICES" not in out
