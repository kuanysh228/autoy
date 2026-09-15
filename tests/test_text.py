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
    "Швейцария только что перестала быть нейтральной. "
    "Берн присоединился к двадцатому пакету санкций против Москвы. "
    "Под ограничения попали банки, нефтяные трейдеры и три верфи. "
    "Эксперты называют это самым жёстким шагом за десятилетие. "
    "Кто здесь прав? "
    "И это только первый шаг."
)


def test_preprocess_strips_voice_config_and_keeps_narration():
    text = """
    Конфигурация озвучки:
    voice=ru-RU-DmitryNeural
    rate=-8%
    style=newscast

    Никто не ожидал такого поворота: рынки резко отреагировали на новое решение регулятора.
    Инвесторы начали пересматривать прогнозы, потому что сигнал оказался жестче ожиданий.
    Для обычных людей это может означать более дорогие кредиты и осторожность бизнеса.
    Главный вопрос теперь в том, готова ли экономика выдержать такую нагрузку?
    """
    clean = prepare_voiceover_text(text, min_chars=120)
    assert "voice" not in clean.lower()
    assert "newscast" not in clean.lower()
    assert "Никто не ожидал" in clean


def test_prepare_rejects_pure_config():
    with pytest.raises(TextQualityError):
        prepare_voiceover_text('{"voice": "ru-RU-DmitryNeural", "rate": "-8%"}', min_chars=10)


def test_prepare_rejects_wrong_language():
    with pytest.raises(TextQualityError):
        prepare_voiceover_text("This is clearly an English paragraph. " * 8, lang="ru", min_chars=10)


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
    assert expected in preprocess(raw)


def test_preprocess_removes_urls_and_refs():
    assert preprocess("Сообщает Reuters [1] https://example.com/a — подробности.") == "Сообщает Reuters, подробности."


def test_split_sentences():
    assert split_sentences("Один. Два! Три? Четыре") == ["Один.", "Два!", "Три?", "Четыре"]


def test_truncate_keeps_hook_and_tail():
    result = truncate_to_limit(SCRIPT, limit=200)
    sentences = split_sentences(result)
    assert sentences[0].startswith("Швейцария")
    assert sentences[-2:] == ["Кто здесь прав?", "И это только первый шаг."]
    assert len(result) <= 200


def test_truncate_returns_unchanged_when_short():
    assert truncate_to_limit(SCRIPT, limit=10_000) == SCRIPT


def test_shorten_script_drops_from_middle():
    shorter = shorten_script(SCRIPT, drop=1)
    assert shorter is not None
    sentences = split_sentences(shorter)
    assert len(sentences) == 5
    assert "самым жёстким" not in shorter
    assert sentences[-1] == "И это только первый шаг."


def test_shorten_script_refuses_too_short():
    assert shorten_script("Раз. Два. Три.", drop=1) is None


def test_filler_and_weak_titles():
    assert has_filler("Кроме того, рынок упал.")
    assert not has_filler("Рынок упал.")
    assert is_weak_title("Россия ввела новые пошлины")
    assert is_weak_title("Один два три четыре пять шесть семь восемь девять десять")
    assert not is_weak_title("Это меняет всё: пошлины удвоены")


def test_topic_key_and_overlap():
    assert topic_key("Ukraine Russia war news today") == "ukraine"
    assert title_overlap("Трамп ввёл санкции против Ирана", "Санкции против Ирана расширены") >= 0.5
    assert title_overlap("Биткоин обновил максимум", "Роботы заменяют курьеров") == 0.0


def test_is_latin():
    assert is_latin("Breaking news today")
    assert not is_latin("Срочные новости")


def test_description_and_title_helpers():
    assert clean_for_description("Текст [1] см. https://x.y и mail@x.io") == "Текст см. и"
    assert clip_title("a" * 120) == "a" * 97 + "..."
