from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from notebooklm import NotebookLMClient

from autoy.research.article import Article, parse_article
from autoy.research.prompts import build_article_question, build_research_query
from autoy.research.service import NotebookLMService, ResearchError, ResearchSettings, get_value

log = logging.getLogger(__name__)

ClientFactory = Callable[[float], Awaitable[Any]]


async def _default_client(timeout: float) -> Any:
    return await NotebookLMClient.from_storage(timeout=timeout)


class ResearchPipeline:
    """Web research in a throwaway NotebookLM notebook, answered as a structured article.

    Requires a prior `notebooklm login` (or the NOTEBOOKLM_AUTH_JSON environment variable).
    """

    def __init__(self, settings: ResearchSettings | None = None, client_factory: ClientFactory | None = None) -> None:
        self.settings = settings or ResearchSettings()
        self._client_factory = client_factory or _default_client

    async def run(self, topic: str, language: str = "en", rules: str = "") -> Article:
        # Build the prompts first so an unsupported language fails before any network call.
        research_query = build_research_query(topic, language)
        question = build_article_question(topic, language, rules)

        async with await self._client_factory(self.settings.client_timeout) as client:
            service = NotebookLMService(client, self.settings)
            notebook = await client.notebooks.create(self.settings.notebook_title)
            try:
                return await self._research(service, notebook.id, research_query, question, language)
            finally:
                try:
                    await client.notebooks.delete(notebook.id)
                except Exception as exc:
                    log.warning("Could not delete notebook %s: %s", notebook.id, exc)

    async def _research(self, service: NotebookLMService, notebook_id: str, research_query: str, question: str, language: str) -> Article:
        log.info("Starting web research...")
        research = await service.start_research(notebook_id, research_query)
        task_id = get_value(research, "task_id")
        if not task_id:
            raise ResearchError(f"research started but no task_id was returned: {research}")

        status = await service.wait_research_completed(notebook_id)
        found = get_value(status, "sources", [])
        if not found:
            raise ResearchError("NotebookLM found no sources")
        log.info("Found %d sources, importing...", len(found))

        imported = await service.import_sources(notebook_id, task_id, found)
        source_ids = [sid for sid in (get_value(s, "id") or get_value(s, "source_id") for s in imported) if sid]
        if not source_ids:
            raise ResearchError("sources were imported but no ids were returned")

        ready = await service.wait_sources_ready(notebook_id, source_ids)
        if ready:
            log.info("Ready sources: %d", len(ready))
        else:
            log.info("No source confirmed readiness, asking over the whole notebook")

        await service.configure_fast_answer(notebook_id, language)
        log.info("Generating article...")
        result = await service.ask(notebook_id, question)
        return parse_article(result.answer)
