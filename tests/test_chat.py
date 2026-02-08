"""Tests for chat functionality."""

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.agents.chat import ChatAgent
from app.core.config import ProviderConfig, ProvidersConfig
from app.main import create_app
from app.models.chat import ChatResponse
from app.models.providers import ProviderType
from app.services.providers import ProviderManager


@pytest.fixture
def openai_config() -> ProviderConfig:
    """Create OpenAI provider config for testing."""
    return ProviderConfig(
        enabled=True,
        model="gpt-4o",
        timeout_seconds=30,
        max_retries=2,
    )


@pytest.fixture
def providers_config(openai_config: ProviderConfig) -> ProvidersConfig:
    """Create providers config for testing."""
    return ProvidersConfig(
        openai=openai_config,
        xai=None,
        default_provider="openai",
    )


@pytest.fixture
def provider_manager(providers_config: ProvidersConfig) -> ProviderManager:
    """Create provider manager for testing."""
    return ProviderManager(providers_config)


@pytest.fixture
def chat_agent(provider_manager: ProviderManager) -> ChatAgent:
    """Create chat agent for testing."""
    return ChatAgent(provider_manager)


class TestChatAgent:
    """Test ChatAgent class."""

    @pytest.mark.asyncio
    async def test_chat_with_default_provider(
        self, chat_agent: ChatAgent, provider_manager: ProviderManager, mocker: MockerFixture
    ) -> None:
        """Test chat with default provider."""
        # Mock the Agent.arun response
        mock_response = mocker.MagicMock()
        mock_response.content = "Hello! How can I help you today?"

        mock_agent_class = mocker.patch("app.agents.chat.Agent")
        mock_agent_instance = mocker.MagicMock()
        mock_agent_instance.arun = mocker.AsyncMock(return_value=mock_response)
        mock_agent_class.return_value = mock_agent_instance

        response = await chat_agent.chat("Hello")

        assert isinstance(response, ChatResponse)
        assert response.reply == "Hello! How can I help you today?"
        assert response.provider == ProviderType.OPENAI
        assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_chat_with_specific_provider(
        self, chat_agent: ChatAgent, provider_manager: ProviderManager, mocker: MockerFixture
    ) -> None:
        """Test chat with specific provider."""
        mock_response = mocker.MagicMock()
        mock_response.content = "Test response"

        mock_agent_class = mocker.patch("app.agents.chat.Agent")
        mock_agent_instance = mocker.MagicMock()
        mock_agent_instance.arun = mocker.AsyncMock(return_value=mock_response)
        mock_agent_class.return_value = mock_agent_instance

        response = await chat_agent.chat("Test", provider=ProviderType.OPENAI)

        assert response.reply == "Test response"
        assert response.provider == ProviderType.OPENAI

    @pytest.mark.asyncio
    async def test_chat_response_without_content_attr(
        self, chat_agent: ChatAgent, mocker: MockerFixture
    ) -> None:
        """Test chat when response doesn't have content attribute."""
        mock_response = "Direct string response"

        mock_agent_class = mocker.patch("app.agents.chat.Agent")
        mock_agent_instance = mocker.MagicMock()
        mock_agent_instance.arun = mocker.AsyncMock(return_value=mock_response)
        mock_agent_class.return_value = mock_agent_instance

        response = await chat_agent.chat("Test")

        assert response.reply == "Direct string response"


class TestChatEndpoint:
    """Test chat API endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_chat_endpoint_success(self, client: TestClient, mocker: MockerFixture) -> None:
        """Test successful chat request."""
        mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
        mock_chat.return_value = ChatResponse(
            reply="Hello! I'm here to help.",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
        )

        response = client.post("/chat", json={"message": "Hello"})

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Hello! I'm here to help."
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"

    def test_chat_endpoint_with_provider(self, client: TestClient, mocker: MockerFixture) -> None:
        """Test chat request with specific provider."""
        mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
        mock_chat.return_value = ChatResponse(
            reply="Response",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
        )

        response = client.post("/chat", json={"message": "Test", "provider": "openai"})

        assert response.status_code == 200
        mock_chat.assert_called_once()

    def test_chat_endpoint_invalid_message(self, client: TestClient) -> None:
        """Test chat request with invalid message."""
        response = client.post("/chat", json={})

        assert response.status_code == 422  # Validation error

    def test_chat_endpoint_provider_error(self, client: TestClient, mocker: MockerFixture) -> None:
        """Test chat request when provider fails."""
        from app.services.providers import ProviderNotConfiguredError

        mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
        mock_chat.side_effect = ProviderNotConfiguredError("Provider not available")

        response = client.post("/chat", json={"message": "Test"})

        assert response.status_code == 400
        assert "Provider not available" in response.json()["detail"]

    def test_chat_endpoint_server_error(self, client: TestClient, mocker: MockerFixture) -> None:
        """Test chat request when server error occurs."""
        mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
        mock_chat.side_effect = Exception("Something went wrong")

        response = client.post("/chat", json={"message": "Test"})

        assert response.status_code == 500
        assert "Chat request failed" in response.json()["detail"]
