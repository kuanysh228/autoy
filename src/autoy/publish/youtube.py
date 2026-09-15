from __future__ import annotations

import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path

from autoy.channels import Channel
from autoy.config import Settings
from autoy.models import NewsItem
from autoy.text import clean_for_description, clip_title

log = logging.getLogger(__name__)

SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
)
CATEGORY_NEWS_AND_POLITICS = "25"
_RETRYABLE_HTTP = frozenset({500, 502, 503, 504})
_ATTEMPTS = 3


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    category_id: str = CATEGORY_NEWS_AND_POLITICS

    def body(self, publish_at: str | None) -> dict:
        status: dict = {"privacyStatus": "private" if publish_at else "public", "selfDeclaredMadeForKids": False}
        if publish_at:
            status["publishAt"] = publish_at
        return {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "tags": self.tags,
                "categoryId": self.category_id,
            },
            "status": status,
        }


def shorts_metadata(news: NewsItem, channel: Channel) -> VideoMetadata:
    direction_tag = news.direction.strip().lstrip("#")
    base_hashtags = "#Shorts #News #WorldNews" if channel.is_english else "#Shorts #Новости #News"
    extra = list(channel.hashtags) or ["news", "shorts"]
    description = (
        f"{clean_for_description(news.text)}\n\n"
        f"{'#' + direction_tag + ' ' if direction_tag else ''}{base_hashtags}\n\n"
        f"{channel.name}\n" + " ".join(f"#{tag}" for tag in extra)
    )
    tags = (["shorts", "news", "world news"] if channel.is_english else ["shorts", "новости", "news"]) + extra
    if direction_tag:
        tags.insert(0, direction_tag)
    return VideoMetadata(title=clip_title(f"{news.title} #Shorts"), description=description, tags=tags)


def shorts_url(video_id: str) -> str:
    return f"https://youtube.com/shorts/{video_id}"


def watch_url(video_id: str) -> str:
    return f"https://youtube.com/watch?v={video_id}"


def _client_id_from_secret(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for key in ("installed", "web"):
        if key in data:
            return data[key].get("client_id", "")
    return ""


class YouTubeClient:
    def __init__(self, settings: Settings, channel: Channel) -> None:
        self.settings = settings
        self.channel = channel
        self._service = None

    @property
    def token_path(self) -> Path:
        return self.channel.token_path(self.settings)

    @property
    def client_secret_path(self) -> Path:
        return self.channel.client_secret_path(self.settings)

    def token_status(self) -> str:
        if not self.token_path.exists():
            return "no token"
        expected = _client_id_from_secret(self.client_secret_path)
        try:
            credentials = pickle.loads(self.token_path.read_bytes())
        except Exception:
            return "unreadable token"
        if expected and getattr(credentials, "client_id", "") != expected:
            return "token issued for another OAuth client"
        return "authorized"

    def authorize_interactively(self, port: int = 8080) -> Path:
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not self.client_secret_path.exists():
            raise FileNotFoundError(f"client secret not found: {self.client_secret_path}")
        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), list(SCOPES))
        credentials = flow.run_local_server(port=port, prompt="select_account", open_browser=True)
        self._save(credentials)
        return self.token_path

    def _save(self, credentials) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_bytes(pickle.dumps(credentials))

    def _load_credentials(self):
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        credentials = None
        if self.token_path.exists():
            credentials = pickle.loads(self.token_path.read_bytes())
            expected = _client_id_from_secret(self.client_secret_path)
            if expected and getattr(credentials, "client_id", "") != expected:
                log.warning("OAuth token %s belongs to another client id, re-authorizing", self.token_path)
                credentials = None

        if credentials and credentials.valid:
            return credentials
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not self.client_secret_path.exists():
                raise FileNotFoundError(f"client secret not found: {self.client_secret_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), list(SCOPES))
            credentials = flow.run_local_server(port=0)
        self._save(credentials)
        return credentials

    def service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("youtube", "v3", credentials=self._load_credentials())
        return self._service

    def upload(self, video_path: Path, metadata: VideoMetadata, publish_at: str | None = None, chunk_mb: int = 1) -> str:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(video_path), chunksize=chunk_mb * 1024 * 1024, resumable=True)
        request = self.service().videos().insert(part="snippet,status", body=metadata.body(publish_at), media_body=media)

        for attempt in range(_ATTEMPTS):
            try:
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        log.info("  Upload: %d%%", int(status.progress() * 100))
                video_id = response["id"]
                log.info("YouTube: uploaded %s", video_id)
                return video_id
            except HttpError as exc:
                if attempt == _ATTEMPTS - 1 or exc.resp.status not in _RETRYABLE_HTTP:
                    raise
                self._backoff(attempt, f"HTTP {exc.resp.status}")
            except (TimeoutError, OSError) as exc:
                if attempt == _ATTEMPTS - 1:
                    raise
                self._backoff(attempt, type(exc).__name__)
        raise RuntimeError("upload failed after retries")

    @staticmethod
    def _backoff(attempt: int, reason: str) -> None:
        delay = 2**attempt
        log.warning("%s, retrying in %ds", reason, delay)
        time.sleep(delay)

    def set_thumbnail(self, video_id: str, thumbnail_path: Path) -> bool:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        try:
            media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            self.service().thumbnails().set(videoId=video_id, media_body=media).execute()
        except HttpError as exc:
            log.warning("Thumbnail not set (scope or quota issue?): %s", exc)
            return False
        log.info("Thumbnail set: %s", thumbnail_path.name)
        return True
