import pytest

from autoy.text import (
    TextQualityError,
    clean_for_description,
    clip_title,
    has_filler,
    is_latin,
    is_weak_title,
    prepare_voiceover_text,
    preprocess,
    shorten_script,
    split_sentences,
    title_overlap,
    topic_key,
    truncate_to_limit,
)

SCRIPT = (
    "Switzerland just stopped being neutral. "
    "Bern joined the twentieth package of sanctions against Moscow. "
    "Banks, oil traders and three shipyards are now restricted. "
    "Experts call it the toughest step in a decade. "
    "Who is right here? "
    "And this is only the first step."
)

RU_SCRIPT = (
    "Швейцария только что перестала быть нейтральной. "
    "Берн присоединился к двадцатому пакету санкций против Москвы. "
    "Под ограничения попали банки, нефтяные трейдеры и три верфи. "
    "Эксперты называют это самым жёстким шагом за десятилетие. "
    "Кто здесь прав? "
    "И это только первый шаг."
)


def test_preprocess_strips_voice_config_and_keeps_narration():
    text = """
    Voice configuration:
    voice=en-US-AriaNeural
    rate=-5%
    style=newscast

    Nobody expected this turn: markets reacted sharply to the regulator's new decision.
    Investors started revising their forecasts because the signal was tougher than expected.
    For ordinary people this could mean more expensive loans and a cautious business climate.
    The main question now is whether the economy can withstand such a load?
    """
    clean = prepare_voiceover_text(text, min_chars=120)
    assert "voice" not in clean.lower()
    assert "newscast" not in clean.lower()
    assert "Nobody expected this turn" in clean


def test_prepare_rejects_pure_config():
    with pytest.raises(TextQualityError):
        prepare_voiceover_text('{"voice": "en-US-AriaNeural", "rate": "-5%"}', min_chars=10)


def test_prepare_rejects_wrong_language():
    with pytest.raises(TextQualityError):
        prepare_voiceover_text(RU_SCRIPT, lang="en", min_chars=10)
    with pytest.raises(TextQualityError):
        prepare_voiceover_text("This is clearly an English paragraph. " * 8, lang="ru", min_chars=10)


def test_preprocess_removes_urls_and_refs():
    assert preprocess("Reuters reports [1] https://example.com/a — details.") == "Reuters reports — details."


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$12,5 млрд", "12,5 миллиарда долларов"),
        ("рост на 15%", "рост на 15 процентов"),
        ("80 000 человек", "80000 человек"),
        ("ИИ меняет рынок", "искусственный интеллект меняет рынок"),
        ("цены 3–5 долларов", "цены от 3 до 5 долларов"),
    ],
)
def test_preprocess_normalizes_russian(raw, expected):
    assert expected in preprocess(raw, lang="ru")


def test_split_sentences():
    assert split_sentences("One. Two! Three? Four") == ["One.", "Two!", "Three?", "Four"]


def test_truncate_keeps_hook_and_tail():
    result = truncate_to_limit(SCRIPT, limit=200)
    sentences = split_sentences(result)
    assert sentences[0].startswith("Switzerland")
    assert sentences[-2:] == ["Who is right here?", "And this is only the first step."]
    assert len(result) <= 200


def test_truncate_returns_unchanged_when_short():
    assert truncate_to_limit(SCRIPT, limit=10_000) == SCRIPT


def test_shorten_script_drops_from_middle():
    shorter = shorten_script(SCRIPT, drop=1)
    assert shorter is not None
    sentences = split_sentences(shorter)
    assert len(sentences) == 5
    assert "toughest step" not in shorter
    assert sentences[-1] == "And this is only the first step."


def test_shorten_script_refuses_too_short():
    assert shorten_script("One. Two. Three.", drop=1) is None


def test_filler_and_weak_titles():
    assert has_filler("Furthermore, the market fell.")
    assert has_filler("Кроме того, рынок упал.")
    assert not has_filler("The market fell.")
    assert is_weak_title("Russia imposes new tariffs")
    assert is_weak_title("Россия ввела новые пошлины")
    assert is_weak_title("one two three four five six seven eight nine ten")
    assert not is_weak_title("This changes everything: tariffs doubled")


def test_topic_key_and_overlap():
    assert topic_key("Ukraine Russia war news today") == "ukraine"
    assert title_overlap("Trump imposes sanctions against Iran", "Sanctions against Iran expanded") >= 0.5
    assert title_overlap("Bitcoin hits new record", "Robots replace couriers") == 0.0
    assert title_overlap("Трамп ввёл санкции против Ирана", "Санкции против Ирана расширены") >= 0.5


def test_is_latin():
    assert is_latin("Breaking news today")
    assert not is_latin("Срочные новости")


def test_description_and_title_helpers():
    assert clean_for_description("Text [1] see https://x.y and mail@x.io") == "Text see and"
    assert clip_title("a" * 120) == "a" * 97 + "..."
