# ObsidianEcho-AI

A standalone FastAPI service that provides AI-powered agents to generate ready-to-import Obsidian markdown notes. Built with the [agno](https://docs.agno.com/) agentic framework for multi-provider AI support.

## Overview

ObsidianEcho-AI acts as a bridge between AI capabilities and Obsidian vaults, enabling automated research, content generation, and note creation workflows. Submit tasks to specialized agents via REST API and receive properly formatted markdown notes ready for import into Obsidian.

## Key Features

- **Multi-Agent System**: Research and template-based note generation agents
- **Multi-Provider AI**: Support for OpenAI, XAI, and more via agno framework
- **Built-in Web Search**: Native web search capabilities through AI providers
- **Async Processing**: Background task queue for long-running operations
- **Webhook Notifications**: Get notified when tasks complete
- **Rate Limiting**: Control usage and costs per API key
- **Request History**: Track all operations and costs
- **API Key Auth**: Simple, secure authentication
- **Obsidian-Native**: All outputs are valid Obsidian markdown with frontmatter

## Technology Stack

- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Package Manager**: uv
- **Agentic Framework**: agno
- **Templating**: Jinja2
- **Testing**: pytest

## Documentation

- **[Project Overview](docs/PROJECT_OVERVIEW.md)** - Architecture, goals, and design principles
- **[Features](docs/FEATURES.md)** - Detailed feature descriptions and API design
- **[Implementation Stories](docs/STORIES.md)** - Step-by-step development roadmap

## Quick Start

### Prerequisites

- Python 3.11 or higher
- uv package manager ([installation guide](https://github.com/astral-sh/uv))
- API keys for AI providers (OpenAI and/or XAI)

### Installation

#### Option 1: Local Development with uv

```bash
# Clone the repository
git clone https://github.com/yourusername/ObsidianEcho-AI.git
cd ObsidianEcho-AI

# Install dependencies with uv
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys:
#   OPENAI_API_KEY=sk-your-key-here
```

#### Option 2: Docker

```bash
# Clone the repository
git clone https://github.com/yourusername/ObsidianEcho-AI.git
cd ObsidianEcho-AI

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys

# Run with docker-compose
docker-compose up -d
```

### Running the Service

#### With uv (Local Development)

```bash
# Set your API key
export OPENAI_API_KEY="sk-your-key-here"

# Run the service
uv run python -m app.main

# Service will be available at http://localhost:8000
# API documentation at http://localhost:8000/docs
```

#### With Docker

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Project Status

**Current Status**: 🏗️ In Development

This project is currently being built following the implementation stories in [docs/STORIES.md](docs/STORIES.md).

### Roadmap

- [ ] **Story 1**: Project Foundation & Setup
- [ ] **Story 2**: AI Provider Integration with agno
- [ ] **Story 3**: API Authentication & Security
- [ ] **Story 4**: Research Agent Core Implementation
- [ ] **Story 5**: Research Agent API Endpoints
- [ ] **Story 6**: Template Agent with Jinja2
- [ ] **Story 7**: Template Agent API Endpoints
- [ ] **Story 8**: Asynchronous Task Queue System
- [ ] **Story 9**: Task Management API Endpoints
- [ ] **Story 10**: Rate Limiting System
- [ ] **Story 11**: Request History & Logging
- [ ] **Story 12**: Webhook Notification System

See [docs/STORIES.md](docs/STORIES.md) for complete roadmap.

## Example Usage

### Research Agent

```bash
curl -X POST http://localhost:8000/agents/research \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Latest developments in quantum computing",
    "depth": "standard"
  }'
```

### Template Agent

```bash
curl -X POST http://localhost:8000/agents/template \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "meeting_notes",
    "variables": {
      "meeting_title": "Q1 Planning",
      "participants": ["Alice", "Bob"],
      "date": "2026-02-08"
    }
  }'
```

### Async Task

```bash
# Submit task
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "research",
    "topic": "AI safety research overview",
    "depth": "deep"
  }'

# Check status
curl http://localhost:8000/tasks/{task_id} \
  -H "Authorization: Bearer your_api_key"

# Get result
curl http://localhost:8000/tasks/{task_id}/result \
  -H "Authorization: Bearer your_api_key"
```

## Configuration

### Environment Variables

API keys **must** be set via environment variables:

```bash
# Required
export OPENAI_API_KEY="sk-your-openai-key"

# Optional (if using XAI/Grok)
export XAI_API_KEY="xai-your-xai-key"
```

For Docker, set these in a `.env` file (see `.env.example`).

### Configuration Files

Additional settings are managed through `config/main.yaml`:

- Provider settings (model names, timeouts, retries)
- Server settings (host, port, debug mode)
- Logging configuration
- CORS settings

See `config/example.yaml` for all available options.

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app

# Run specific test file
uv run pytest tests/test_agents.py
```

### Code Quality

```bash
# Lint with ruff
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy app/
```

## Contributing

This is currently a personal project. Contributions, suggestions, and feedback are welcome through issues and pull requests.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [agno](https://docs.agno.com/) agentic framework
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
- Designed for [Obsidian](https://obsidian.md/)

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/ObsidianEcho-AI/issues)
- **Documentation**: [docs/](docs/)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ObsidianEcho-AI/discussions)

---

**Note**: This project is under active development. The API and features may change as development progresses. Check the [STORIES.md](docs/STORIES.md) for the current implementation status.
