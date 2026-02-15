"""Tests for research agent and endpoint."""

import pytest
from agno.agent import RunOutput
from agno.models.message import Citations, UrlCitation
from agno.models.metrics import Metrics
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.agents.research import ResearchAgent
from app.core.config import ProviderConfig, ProvidersConfig
from app.main import create_app
from app.models.providers import ProviderType
from app.models.research import ResearchDepth, ResearchMetadata, ResearchResponse, SourceReference
from app.services.providers import (
    ProviderExecutionError,
    ProviderManager,
    ProviderNotConfiguredError,
)


@pytest.fixture
def providers_config() -> ProvidersConfig:
    """Create provider config for research tests."""
    return ProvidersConfig(
        openai=ProviderConfig(enabled=True, model="gpt-4o", timeout_seconds=30, max_retries=2),
        xai=None,
        default_provider="openai",
    )


@pytest.fixture
def provider_manager(providers_config: ProvidersConfig) -> ProviderManager:
    """Create provider manager fixture."""
    return ProviderManager(providers_config)


@pytest.fixture
def research_agent(provider_manager: ProviderManager) -> ResearchAgent:
    """Create research agent fixture."""
    return ResearchAgent(provider_manager)


class TestResearchAgent:
    """Unit tests for research agent behavior."""

    @pytest.mark.asyncio
    async def test_research_formats_obsidian_markdown(
        self,
        research_agent: ResearchAgent,
        provider_manager: ProviderManager,
        mocker: MockerFixture,
    ) -> None:
        """Research result should include frontmatter and sources section."""
        run_output = RunOutput(
            content="# Quantum Computing\n\n## Overview\n\nSummary text.",
            model="gpt-4o",
            metrics=Metrics(total_tokens=321, duration=1.23),
            citations=Citations(
                urls=[
                    UrlCitation(url="https://example.com/one", title="Source One"),
                    UrlCitation(url="https://example.com/two", title="Source Two"),
                ]
            ),
        )

        mocker.patch.object(
            provider_manager,
            "run_with_fallback",
            new=mocker.AsyncMock(return_value=(run_output, ProviderType.OPENAI)),
        )

        result = await research_agent.research(topic="Quantum Computing")

        assert result.topic == "Quantum Computing"
        assert result.metadata.provider == ProviderType.OPENAI
        assert result.metadata.tokens_used == 321
        assert result.metadata.sources_count == 2
        assert result.markdown.startswith("---\n")
        assert "agent: research" in result.markdown
        assert "## Sources" in result.markdown
        assert "https://example.com/one" in result.markdown

    @pytest.mark.asyncio
    async def test_research_adds_heading_and_missing_sources_note(
        self,
        research_agent: ResearchAgent,
        provider_manager: ProviderManager,
        mocker: MockerFixture,
    ) -> None:
        """Research formatting should add heading and source note if missing."""
        run_output = RunOutput(
            content="Overview only without heading.",
            model="gpt-4o",
            metrics=Metrics(total_tokens=10, duration=0.1),
            citations=None,
        )

        mocker.patch.object(
            provider_manager,
            "run_with_fallback",
            new=mocker.AsyncMock(return_value=(run_output, ProviderType.OPENAI)),
        )

        result = await research_agent.research(topic="AI safety")

        assert "# AI safety" in result.markdown
        assert "No explicit citations were returned" in result.markdown
        assert result.sources == []


class TestResearchEndpoint:
    """Integration tests for research endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(create_app())

    def test_research_endpoint_success(self, client: TestClient, mocker: MockerFixture) -> None:
        """Test successful research request."""
        response_payload = ResearchResponse(
            topic="AI safety",
            markdown="---\ntitle: AI safety\n---\n\n# AI safety",
            sources=[SourceReference(url="https://example.com", title="Example")],
            metadata=ResearchMetadata(
                provider=ProviderType.OPENAI,
                model="gpt-4o",
                depth=ResearchDepth.STANDARD,
                duration_seconds=1.1,
                tokens_used=123,
                sources_count=1,
            ),
        )

        mock_research = mocker.patch("app.api.routes.research.research_agent.research")
        mock_research.return_value = response_payload

        response = client.post(
            "/agents/research",
            json={"topic": "AI safety", "depth": "standard"},
            headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "AI safety"
        assert data["metadata"]["provider"] == "openai"

    def test_research_endpoint_validation_error(self, client: TestClient) -> None:
        """Test validation error for invalid request."""
        response = client.post(
            "/agents/research",
            json={"topic": "AI"},
            headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"},
        )

        assert response.status_code == 422

    def test_research_endpoint_provider_error(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test provider-not-configured mapped to 400."""
        mock_research = mocker.patch("app.api.routes.research.research_agent.research")
        mock_research.side_effect = ProviderNotConfiguredError("Provider not available")

        response = client.post(
            "/agents/research",
            json={"topic": "AI safety"},
            headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"},
        )

        assert response.status_code == 400

    def test_research_endpoint_provider_execution_error(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test all-providers-failed mapped to 502."""
        mock_research = mocker.patch("app.api.routes.research.research_agent.research")
        mock_research.side_effect = ProviderExecutionError(
            message="All provider execution attempts failed: openai, xai",
            attempted_providers=[ProviderType.OPENAI, ProviderType.XAI],
            last_error=RuntimeError("boom"),
        )

        response = client.post(
            "/agents/research",
            json={"topic": "AI safety"},
            headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"},
        )

        assert response.status_code == 502

    def test_research_endpoint_server_error(
        self, client: TestClient, mocker: MockerFixture
    ) -> None:
        """Test unexpected exceptions mapped to 500."""
        mock_research = mocker.patch("app.api.routes.research.research_agent.research")
        mock_research.side_effect = Exception("Unexpected")

        response = client.post(
            "/agents/research",
            json={"topic": "AI safety"},
            headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"},
        )

        assert response.status_code == 500

    def test_research_endpoint_requires_auth(self, client: TestClient) -> None:
        """Research endpoint requires authentication."""
        response = client.post("/agents/research", json={"topic": "AI safety"})

        assert response.status_code == 401
