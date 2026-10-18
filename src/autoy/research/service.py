from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from notebooklm import ChatGoal, ChatResponseLength

from autoy.research.prompts import editor_prompt

log = logging.getLogger(__name__)

T = TypeVar("T")


class ResearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResearchSettings:
    research_timeout: float = 70
    source_process_timeout: float = 60
    chat_timeout: float = 120
    client_timeout: float = 120
    poll_interval: float = 5
    # More sources means a proportionally slower answer: raise chat_timeout together with it.
    max_sources: int = 2
    notebook_title: str = "autoy research"


def get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


async def run_with_timeout(coro: Awaitable[T], timeout: float, error_text: str) -> T:
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError as exc:
        raise TimeoutError(error_text) from exc


class NotebookLMService:
    """Thin async wrapper around the NotebookLM client."""

    def __init__(self, client: Any, settings: ResearchSettings) -> None:
        self.client = client
        self.settings = settings

    async def start_research(self, notebook_id: str, query: str) -> Any:
        return await run_with_timeout(
            self.client.research.start(notebook_id, query=query, source="web", mode="fast"),
            timeout=30,
            error_text="web research did not start in time",
        )

    async def wait_research_completed(self, notebook_id: str) -> Any:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.settings.research_timeout
        while True:
            status = await run_with_timeout(
                self.client.research.poll(notebook_id),
                timeout=30,
                error_text="polling the research status timed out",
            )
            current = get_value(status, "status")
            if current == "completed":
                return status
            if current == "no_research":
                raise ResearchError("NotebookLM reports no active research task")
            if loop.time() >= deadline:
                raise TimeoutError("research did not finish in time")
            log.info("Research in progress...")
            await asyncio.sleep(self.settings.poll_interval)

    async def import_sources(self, notebook_id: str, task_id: str, sources: Sequence[Any]) -> Any:
        return await run_with_timeout(
            self.client.research.import_sources(notebook_id, task_id, list(sources)[: self.settings.max_sources]),
            timeout=40,
            error_text="importing sources timed out",
        )

    async def wait_sources_ready(self, notebook_id: str, source_ids: Sequence[str]) -> list[str]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.settings.source_process_timeout
        while True:
            ready: list[str] = []
            for source_id in source_ids:
                try:
                    fulltext = await asyncio.wait_for(self.client.sources.get_fulltext(notebook_id, source_id), timeout=12)
                except Exception:
                    continue
                if get_value(fulltext, "content", ""):
                    ready.append(source_id)
            if ready:
                return ready
            if loop.time() >= deadline:
                return []
            log.info("Sources are still being processed...")
            await asyncio.sleep(self.settings.poll_interval)

    async def configure_fast_answer(self, notebook_id: str, language: str) -> None:
        try:
            await asyncio.wait_for(
                self.client.chat.configure(
                    notebook_id,
                    goal=ChatGoal.CUSTOM,
                    response_length=ChatResponseLength.SHORTER,
                    custom_prompt=editor_prompt(language),
                ),
                timeout=20,
            )
        except Exception as exc:
            log.warning("Could not configure the chat, using defaults: %s", exc)

    async def ask(self, notebook_id: str, question: str) -> Any:
        return await run_with_timeout(
            self.client.chat.ask(notebook_id, question=question),
            timeout=self.settings.chat_timeout,
            error_text="the answer took too long",
        )
