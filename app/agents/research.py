"""Research agent for generating Obsidian-ready notes."""

import re
from dataclasses import asdict
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import yaml
from agno.agent import Agent, RunOutput

from app.core.logging import get_logger
from app.models.providers import ProviderType
from app.models.research import (
    ResearchDepth,
    ResearchMetadata,
    ResearchResponse,
    SourceReference,
)
from app.services.providers import ProviderManager

logger = get_logger(__name__)


class ResearchAgent:
    """AI research agent with provider-native web-search support."""

    def __init__(self, provider_manager: ProviderManager) -> None:
        """Initialize research agent."""
        self.provider_manager = provider_manager

    def _build_instructions(self, depth: ResearchDepth, focus_areas: list[str]) -> list[str]:
        depth_instruction = {
            ResearchDepth.QUICK: "Keep the analysis concise. Focus on 3-5 key points.",
            ResearchDepth.STANDARD: "Provide balanced coverage with clear key points and practical implications.",
            ResearchDepth.DEEP: "Provide deep analysis with nuanced trade-offs, competing views, and detailed evidence.",
        }[depth]

        instructions = [
            "You are a research analyst producing Obsidian markdown notes.",
            "Use web search capability to gather current, credible sources.",
            "Cite claims with links whenever possible.",
            "Structure output with sections: Overview, Key Points, Details, Sources.",
            depth_instruction,
            "Use markdown only in your response.",
        ]

        if focus_areas:
            instructions.append(f"Prioritize these focus areas: {', '.join(focus_areas)}")

        return instructions

    def _build_prompt(self, topic: str, depth: ResearchDepth, focus_areas: list[str]) -> str:
        prompt_lines = [
            f"Research topic: {topic}",
            f"Depth: {depth.value}",
            "Produce an Obsidian-compatible note with citations and links.",
        ]
        if focus_areas:
            prompt_lines.append(f"Focus areas: {', '.join(focus_areas)}")
        return "\n".join(prompt_lines)

    @staticmethod
    def _strip_wrapping_markdown_fence(body: str) -> str:
        """Strip a single wrapping fenced markdown block if present."""
        text = body.strip()
        fenced_match = re.match(r"^```(?:markdown|md)?\s*\n(?P<body>[\s\S]*?)\n```$", text)
        if fenced_match:
            return fenced_match.group("body").strip()
        return text

    @staticmethod
    def _extract_sources(run_output: RunOutput) -> list[SourceReference]:
        citations = getattr(run_output, "citations", None)
        urls = getattr(citations, "urls", None) if citations is not None else None

        if not urls:
            return []

        deduped: dict[str, SourceReference] = {}
        for citation in urls:
            citation_data = asdict(citation) if hasattr(citation, "__dataclass_fields__") else {}
            url = citation_data.get("url") or getattr(citation, "url", None)
            title = citation_data.get("title") or getattr(citation, "title", None)
            if url and url not in deduped:
                deduped[url] = SourceReference(url=url, title=title)

        return list(deduped.values())

    @staticmethod
    def _extract_title(topic: str, body: str) -> str:
        heading_match = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()
        return topic.strip()

    @staticmethod
    def _render_frontmatter(
        *,
        title: str,
        topic: str,
        depth: ResearchDepth,
        provider: ProviderType,
        model: str,
        sources: list[SourceReference],
    ) -> str:
        frontmatter = {
            "title": title,
            "topic": topic,
            "date": datetime.now(UTC).date().isoformat(),
            "tags": ["research", "ai-generated"],
            "source": "ObsidianEcho-AI",
            "agent": "research",
            "depth": depth.value,
            "provider": provider.value,
            "model": model,
            "sources": [source.url for source in sources],
        }

        yaml_block = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False).strip()
        return f"---\n{yaml_block}\n---"

    @staticmethod
    def _append_sources_if_missing(body: str, sources: list[SourceReference]) -> str:
        if re.search(r"^##\s+Sources\b", body, flags=re.MULTILINE):
            return body

        if not sources:
            return f"{body}\n\n## Sources\n\n- No explicit citations were returned by the provider."

        lines = []
        for index, source in enumerate(sources, start=1):
            title = source.title if source.title else source.url
            lines.append(f"{index}. [{title}]({source.url})")

        sources_section = "\n".join(lines)
        return f"{body}\n\n## Sources\n\n{sources_section}"

    def _format_markdown(
        self,
        *,
        topic: str,
        depth: ResearchDepth,
        provider: ProviderType,
        model: str,
        body: str,
        sources: list[SourceReference],
    ) -> str:
        normalized_body = self._strip_wrapping_markdown_fence(body)
        title = self._extract_title(topic, normalized_body)

        if not re.search(r"^#\s+", normalized_body, flags=re.MULTILINE):
            normalized_body = f"# {title}\n\n{normalized_body}"

        normalized_body = self._append_sources_if_missing(normalized_body, sources)
        frontmatter = self._render_frontmatter(
            title=title,
            topic=topic,
            depth=depth,
            provider=provider,
            model=model,
            sources=sources,
        )

        return f"{frontmatter}\n\n{normalized_body}\n"

    async def _run_research_with_provider(
        self,
        *,
        topic: str,
        depth: ResearchDepth,
        focus_areas: list[str],
        provider: ProviderType,
    ) -> RunOutput:
        model = self.provider_manager.get_research_model(provider=provider, depth=depth)

        agent = Agent(
            model=model,
            instructions=self._build_instructions(depth=depth, focus_areas=focus_areas),
            markdown=True,
        )

        return await agent.arun(
            self._build_prompt(topic=topic, depth=depth, focus_areas=focus_areas)
        )

    async def research(
        self,
        *,
        topic: str,
        depth: ResearchDepth = ResearchDepth.STANDARD,
        provider: ProviderType | None = None,
        focus_areas: list[str] | None = None,
    ) -> ResearchResponse:
        """Run research and return Obsidian-ready markdown + metadata."""
        start = perf_counter()
        focus_areas = focus_areas or []

        run_output, used_provider = await self.provider_manager.run_with_fallback(
            operation=lambda candidate: self._run_research_with_provider(
                topic=topic,
                depth=depth,
                focus_areas=focus_areas,
                provider=candidate,
            ),
            preferred_provider=provider,
        )

        body = str(run_output.content) if getattr(run_output, "content", None) is not None else ""
        sources = self._extract_sources(run_output)

        model_name = getattr(
            run_output, "model", None
        ) or self.provider_manager.get_research_model_name(provider=used_provider, depth=depth)

        markdown = self._format_markdown(
            topic=topic,
            depth=depth,
            provider=used_provider,
            model=model_name,
            body=body,
            sources=sources,
        )

        metrics: Any = getattr(run_output, "metrics", None)
        tokens_used = getattr(metrics, "total_tokens", None) if metrics is not None else None
        metric_duration = getattr(metrics, "duration", None) if metrics is not None else None
        elapsed = perf_counter() - start

        metadata = ResearchMetadata(
            provider=used_provider,
            model=model_name,
            depth=depth,
            duration_seconds=float(metric_duration)
            if metric_duration is not None
            else round(elapsed, 4),
            tokens_used=tokens_used,
            sources_count=len(sources),
        )

        logger.info(
            "Research completed",
            extra={
                "topic": topic,
                "provider": used_provider.value,
                "model": model_name,
                "depth": depth.value,
                "sources": len(sources),
            },
        )

        return ResearchResponse(
            topic=topic,
            markdown=markdown,
            sources=sources,
            metadata=metadata,
        )
