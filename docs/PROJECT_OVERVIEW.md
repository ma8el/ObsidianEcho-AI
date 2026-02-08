# ObsidianEcho-AI Project Overview

## Vision

ObsidianEcho-AI is a standalone FastAPI service that provides AI-powered agents to generate ready-to-import Obsidian markdown notes. The service acts as a bridge between AI capabilities and Obsidian vaults, enabling users to automate research, content generation, and note creation workflows.

## Core Concept

Users interact with the API by submitting tasks to specialized agents. Each agent performs specific operations (research, template filling, etc.) and returns properly formatted markdown notes that can be directly imported into Obsidian vaults. The service handles long-running operations asynchronously and can notify external systems when tasks complete.

## Architecture

### Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Package Manager**: uv
- **Agentic Framework**: [agno](https://docs.agno.com/) - Provides agent orchestration, multi-provider AI support, and built-in capabilities
- **AI Providers**: OpenAI (GPT-4+), XAI (Grok) via agno
- **Web Search**: Built-in web search capabilities from AI providers via agno
- **Templating**: Jinja2 for template-based note generation
- **Task Queue**: Async background task processing
- **Storage**: File-based YAML/JSON configuration
- **Authentication**: API key-based
- **Testing**: pytest

### High-Level Architecture

```
┌─────────────────┐
│   API Client    │
│  (User/Script)  │
└────────┬────────┘
         │
         │ HTTP/REST + API Key
         ▼
┌─────────────────────────────────────┐
│        FastAPI Service              │
│  ┌────────────────────────────────┐ │
│  │   API Endpoints                │ │
│  │  - /agents/research            │ │
│  │  - /agents/template            │ │
│  │  - /tasks/{id}                 │ │
│  └──────────────┬─────────────────┘ │
│                 │                    │
│  ┌──────────────▼─────────────────┐ │
│  │   Authentication & Rate Limit  │ │
│  └──────────────┬─────────────────┘ │
│                 │                    │
│  ┌──────────────▼─────────────────┐ │
│  │      Task Queue Manager        │ │
│  │  - Async task handling         │ │
│  │  - Status tracking             │ │
│  └──────────────┬─────────────────┘ │
│                 │                    │
│  ┌──────────────▼─────────────────┐ │
│  │        agno Framework          │ │
│  │  ┌──────────────────────────┐  │ │
│  │  │  Research Agent          │  │ │
│  │  │  - Web search + LLM      │  │ │
│  │  │  - Summarization         │  │ │
│  │  └──────────────────────────┘  │ │
│  │  ┌──────────────────────────┐  │ │
│  │  │  Template Agent          │  │ │
│  │  │  - Prompt generation     │  │ │
│  │  │  - Jinja2 rendering      │  │ │
│  │  └──────────────────────────┘  │ │
│  └────────────────┬───────────────┘ │
└───────────────────┼─────────────────┘
                    │
         ┌──────────▼──────────┐
         │   AI Providers      │
         │   - OpenAI (GPT-4+) │
         │   - XAI (Grok)      │
         │   Built-in tools    │
         └─────────────────────┘
```

## agno Framework Integration

We leverage [agno](https://docs.agno.com/) as our core agentic framework. This provides:

- **Multi-Provider Support**: Unified interface for OpenAI, XAI, and other providers
- **Built-in Tools**: Native web search, file operations, and other capabilities
- **Agent Orchestration**: Structured agent workflows with state management
- **Streaming Support**: Real-time streaming of agent responses
- **Provider-Specific Features**: Access to provider-native capabilities like OpenAI's web search

By building on agno, we avoid reimplementing provider abstractions and can focus on Obsidian-specific logic.

## Key Design Principles

1. **Stateless API**: Each request contains all necessary information; no session state
2. **Async-First**: Long-running agent tasks execute in background queues
3. **agno-Powered Agents**: All AI interactions go through agno's agent framework
4. **Obsidian-Native Output**: All agents return valid Obsidian markdown with proper frontmatter
5. **Extensible Agents**: Easy to add new agent types using agno's agent patterns
6. **Observable**: Comprehensive logging and history tracking for all operations

## Target Users

- **Knowledge Workers**: Researchers, writers, students who maintain Obsidian vaults
- **Automation Enthusiasts**: Users building workflows to enhance their note-taking
- **Developers**: Those integrating AI capabilities into their Obsidian workflows via API

## Project Goals

### Primary Goals

1. Provide reliable, multi-provider AI agents for Obsidian note generation using agno
2. Support asynchronous processing for long-running research and generation tasks
3. Enable extensible agent architecture leveraging agno's framework
4. Maintain simple file-based configuration for easy deployment

### Secondary Goals

1. Implement webhook notifications for integration with external systems
2. Track usage and history for debugging and optimization
3. Provide rate limiting to prevent abuse and manage costs
4. Support template libraries for common note patterns

## Non-Goals

- **Not an Obsidian Plugin**: This is a standalone service, not embedded in Obsidian
- **Not a Note Manager**: Does not store, index, or manage Obsidian vaults directly
- **Not a Full CMS**: Focused on note generation, not content management
- **Not Multi-Tenant SaaS**: Designed for personal/small team use

## Deployment Model

The service is designed to be deployed as:

- **Local Development**: Run on localhost for personal use
- **Self-Hosted**: Deploy on personal servers or VPS
- **Docker Container**: Containerized deployment for easy hosting
- **Cloud Functions**: Potentially adaptable for serverless deployment

## Success Criteria

1. Generate valid Obsidian markdown notes from agent outputs
2. Support at least 2 AI providers (OpenAI, XAI) via agno
3. Process research requests with built-in web search integration
4. Handle asynchronous tasks reliably with status tracking
5. Authenticate requests and enforce rate limits
6. Provide webhook notifications on task completion
7. Maintain <2s response time for synchronous endpoints
8. Support concurrent task processing

## Future Expansion Possibilities

- Additional agent types (meeting transcripts, content analysis, etc.)
- Vector database integration for semantic note search
- Batch processing for multiple notes
- Obsidian plugin for direct integration
- Multi-vault support
- Scheduled/recurring agent tasks
- Note enhancement agents (improve existing notes)
- Custom agno tools for Obsidian-specific operations
