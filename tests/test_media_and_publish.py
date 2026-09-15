from pathlib import Path

from PIL import Image

from autoy.channels import get_channel
from autoy.media.kenburns import Slideshow, ken_burns
from autoy.media.shorts import is_power_word, karaoke_window, pexels_query_for, pick_music
from autoy.models import NewsItem, WeeklyStory, WordEvent
from autoy.pipeline.weekly import WeekLabel, weekly_metadata, weekly_title
from autoy.publish import shorts_metadata
from autoy.publish.telegram import format_channel_post
from autoy.tts import CappedSpeech


def _image(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (400, 700), color)


def test_ken_burns_keeps_output_size():
    frame = ken_burns(_image((10, 20, 30)), progress=0.5, direction=1, size=(400, 700), zoom=0.1, wide=True)
    assert frame.size == (400, 700)


def test_slideshow_scene_switching_and_crossfade():
    show = Slideshow([_image((255, 0, 0)), _image((0, 0, 255))], (100, 100), scene_seconds=2.0, crossfade_seconds=0.5, zoom=0.0)
    assert show.frame_at(0.0, 10.0).getpixel((0, 0)) == (255, 0, 0)
    assert show.frame_at(2.5, 10.0).getpixel((0, 0)) == (0, 0, 255)
    blended = show.frame_at(1.75, 10.0).getpixel((0, 0))
    assert 0 < blended[0] < 255 and 0 < blended[2] < 255


def test_slideshow_stretches_to_total():
    show = Slideshow(
        [_image((255, 0, 0)), _image((0, 0, 255))], (100, 100), scene_seconds=6.0, crossfade_seconds=0.1, zoom=0.0, stretch_to_total=True
    )
    assert show.frame_at(0.0, 12.0).getpixel((0, 0)) == (255, 0, 0)
    assert show.frame_at(9.0, 12.0).getpixel((0, 0)) == (0, 0, 255)
    assert not Slideshow([], (100, 100), 1, 0.1, 0.0)


def test_karaoke_window_groups_words():
    words = [WordEvent(f"w{i}", float(i), float(i) + 0.9) for i in range(7)]
    window = karaoke_window(words, 4.2)
    assert window.before == ["w3"]
    assert window.current == "w4"
    assert window.after == ["w5"]
    assert karaoke_window([], 1.0).words == []


def test_pexels_query_mapping():
    assert pexels_query_for(NewsItem("x", "y", "#Bitcoin")) == "bitcoin cryptocurrency gold"
    assert pexels_query_for(NewsItem("Удар по Киеву", "ракеты", "#Война")) == "military soldiers conflict"
    assert pexels_query_for(NewsItem("Новые санкции", "против банков", "#Санкции")) == "cargo port containers trade"
    assert pexels_query_for(NewsItem("Quiet day", "nothing", "#Gardening")) == "gardening"
    assert pexels_query_for(NewsItem("Тихо", "ничего", "")) == "breaking news world politics"


def test_power_words():
    assert is_power_word("Санкции,")
    assert is_power_word("$5")
    assert is_power_word("2026")
    assert not is_power_word("сегодня")


def test_pick_music_prefers_subdir(tmp_path: Path):
    (tmp_path / "a.mp3").write_bytes(b"")
    (tmp_path / "calm").mkdir()
    (tmp_path / "calm" / "b.mp3").write_bytes(b"")
    assert pick_music(tmp_path, "calm").name == "b.mp3"
    assert pick_music(tmp_path, "missing").name == "a.mp3"
    assert pick_music(tmp_path / "empty") is None


def test_shorts_metadata():
    news = NewsItem("Это меняет всё: пошлины удвоены", "Текст [1] https://a.b", "#Торговля")
    meta = shorts_metadata(news, get_channel("geo"))
    assert meta.title == "Это меняет всё: пошлины удвоены #Shorts"
    assert meta.tags[0] == "Торговля"
    assert "#Торговля #Shorts #Новости #News" in meta.description
    assert "https://" not in meta.description
    body = meta.body("2026-05-13T16:00:00Z")
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-05-13T16:00:00Z"
    assert meta.body(None)["status"]["privacyStatus"] == "public"


def test_weekly_title_and_chapters():
    stories = [
        WeeklyStory("Украина", "Переговоры сорваны: фронт снова в огне после недели тишины и надежд.", "t", "#x", "q"),
        WeeklyStory("Трамп", "Трамп ввёл пошлины", "t", "#y", "q"),
    ]
    channel = get_channel("geo")
    title = weekly_title(stories, channel)
    assert title.endswith(" — твой мир за неделю")
    assert len(title) <= 100
    meta = weekly_metadata(stories, channel, [5.5, 95.0], WeekLabel.current())
    assert "0:00 Введение" in meta.description
    assert "1:35 Трамп: Трамп ввёл пошлины" in meta.description
    assert "0:05 Украина" in meta.description


def test_channel_post_formatting():
    news = NewsItem("A & B", "x" * 800, "#Tag")
    post = format_channel_post(news)
    assert post.startswith("🔴 <b>A &amp; B</b>")
    assert post.endswith("#Tag")
    assert len(post) < 800


def test_capped_speech_path(tmp_path: Path):
    from autoy.models import Voice
    from autoy.tts import Speech

    capped = CappedSpeech(Speech(tmp_path / "a.mp3", [], Voice("v", "n")), "text")
    assert capped.path == tmp_path / "a.mp3"
