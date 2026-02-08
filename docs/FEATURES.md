# ObsidianEcho-AI Features

## Core Features

### 1. Multi-Provider AI Support

**Description**: Support multiple AI providers through agno framework with seamless switching and fallback capabilities.

**Providers**:
- OpenAI (GPT-4, GPT-4 Turbo, GPT-4o)
- XAI (Grok models)
- Extensible for future providers supported by agno

**Configuration**:
- Provider selection per request or default in config
- API key management for each provider
- Model selection per agent/request
- Automatic fallback to secondary provider on failure

### 2. Research Agent

**Description**: Autonomous agent that researches topics using AI-powered web search and generates comprehensive Obsidian notes with sources.

**Capabilities**:
- **Web Search**: Uses built-in web search from OpenAI/XAI via agno
- **Source Aggregation**: Collects and validates information from multiple sources
- **Summarization**: Creates structured summaries with key points
- **Citation Management**: Automatically formats sources in Obsidian-compatible format
- **Topic Expansion**: Can explore subtopics and related concepts

**Input**:
- Research topic/question
- Depth level (quick, standard, deep)
- Optional focus areas or constraints
- Output format preferences

**Output**:
- Markdown note with frontmatter (title, tags, date, sources)
- Structured sections (Overview, Key Points, Details, Sources)
- Properly formatted links and citations
- Optional Obsidian backlinks to related concepts

### 3. Template Agent

**Description**: Generates notes based on Jinja2 templates with AI-powered content filling.

**Capabilities**:
- **Template Processing**: Jinja2 templating with full feature support
- **AI Content Generation**: Uses LLM to fill template variables intelligently
- **Context-Aware**: Can reference user-provided context or previous notes
- **Dynamic Logic**: Support for conditional sections, loops, and filters
- **Template Library**: Pre-built templates for common note types

**Input**:
- Template (inline or reference to stored template)
- Variables and context data
- AI instructions for content generation
- Optional examples or style guidelines

**Output**:
- Fully rendered markdown note
- All variables populated by AI or provided data
- Proper Obsidian frontmatter
- Formatted according to template structure

**Common Template Types**:
- Meeting notes
- Project briefs
- Article summaries
- Daily/weekly reviews
- Book notes
- Learning journals

### 4. Asynchronous Task Queue

**Description**: Background processing system for long-running agent operations.

**Capabilities**:
- **Non-Blocking Requests**: Submit tasks and receive immediate task ID
- **Status Tracking**: Query task progress (pending, processing, completed, failed)
- **Priority Queue**: Support for task prioritization
- **Concurrent Processing**: Multiple tasks processed in parallel
- **Timeout Management**: Configurable timeouts per agent type
- **Retry Logic**: Automatic retries on transient failures

**Task Lifecycle**:
1. **Submitted**: Task accepted, queued for processing
2. **Processing**: Agent actively working on task
3. **Completed**: Success, result available
4. **Failed**: Error occurred, details in status

**API Endpoints**:
- `POST /tasks` - Submit new task
- `GET /tasks/{task_id}` - Get task status
- `GET /tasks/{task_id}/result` - Retrieve completed result
- `DELETE /tasks/{task_id}` - Cancel pending task
- `GET /tasks` - List all tasks (with filtering)

### 5. Webhook Notifications

**Description**: HTTP callbacks sent when tasks complete or specific events occur.

**Capabilities**:
- **Event Types**: Task completion, task failure, rate limit warnings
- **Configurable Endpoints**: Per-request or global webhook URLs
- **Retry Logic**: Automatic retries on webhook delivery failure
- **Payload Customization**: Include full result or just status
- **Authentication**: Support for webhook secrets and signatures
- **Filtering**: Only notify on specific event types or conditions

**Webhook Payload**:
```json
{
  "event": "task.completed",
  "task_id": "uuid",
  "timestamp": "ISO8601",
  "agent_type": "research",
  "status": "completed",
  "result_url": "/tasks/{task_id}/result",
  "metadata": {}
}
```

### 6. Request History & Logging

**Description**: Comprehensive tracking of all API requests, agent executions, and system events.

**Tracked Information**:
- All API requests with timestamps
- Agent execution details (model, tokens, duration)
- Task lifecycle events
- Errors and warnings
- Cost tracking (estimated per provider)

**Log Levels**:
- **DEBUG**: Detailed agent interactions, provider calls
- **INFO**: Request/response, task status changes
- **WARNING**: Rate limits, retry attempts
- **ERROR**: Failures, exceptions

**Storage**:
- Structured JSON logs to files
- Configurable retention period
- Optional external logging (stdout, file, syslog)

**Query Capabilities**:
- Filter by date range, agent type, status
- Search by task ID or API key
- Aggregate statistics (requests/day, success rate, etc.)

### 7. Rate Limiting

**Description**: Control API usage to prevent abuse and manage costs.

**Strategies**:
- **Per API Key**: Limit requests per key per time window
- **Global Limits**: Overall system capacity limits
- **Per Agent Type**: Different limits for research vs template agents
- **Token-Based**: Track and limit AI provider token usage
- **Cost-Based**: Limit by estimated cost per period

**Configuration**:
```yaml
rate_limits:
  default:
    requests_per_minute: 10
    requests_per_hour: 100
    tokens_per_day: 100000
  research_agent:
    requests_per_minute: 5
    max_concurrent: 3
```

**Responses**:
- HTTP 429 when limit exceeded
- `Retry-After` header with wait time
- Current limit status in response headers

### 8. API Key Authentication

**Description**: Secure API access using key-based authentication.

**Features**:
- **Key Generation**: Create keys with optional names/descriptions
- **Scoping**: Limit keys to specific agent types or endpoints
- **Expiration**: Optional expiration dates for keys
- **Revocation**: Instantly disable compromised keys
- **Rate Limit Association**: Per-key rate limit tracking

**Key Format**:
- `oea_` prefix for identification
- Random secure tokens
- Stored securely with hashing

**Usage**:
```
Authorization: Bearer oea_your_api_key_here
```

### 9. Configuration Management

**Description**: File-based configuration using YAML for easy customization.

**Configuration Files**:
- `config/main.yaml` - Core service settings
- `config/providers.yaml` - AI provider credentials and settings
- `config/agents.yaml` - Agent-specific configuration
- `config/templates/` - Template library directory

**Hot Reload**: Certain config changes take effect without restart.

### 10. Obsidian Markdown Output

**Description**: All agents produce valid, well-formatted Obsidian markdown notes.

**Standard Output Format**:
```markdown
---
title: Note Title
date: 2026-02-08
tags: [ai-generated, research]
source: ObsidianEcho-AI
agent: research
---

# Note Title

## Section 1

Content with [[internal links]] and [external links](https://example.com).

## Sources

1. Source 1 - [Link](url)
2. Source 2 - [Link](url)
```

**Features**:
- YAML frontmatter with metadata
- Proper heading hierarchy
- Obsidian-style internal links `[[note]]`
- Tag support
- Code blocks with syntax highlighting
- Tables, lists, and formatting
- Callouts/admonitions when appropriate

## API Design

### RESTful Endpoints

**Agent Execution**:
- `POST /agents/research` - Execute research agent
- `POST /agents/template` - Execute template agent

**Task Management**:
- `POST /tasks` - Submit async task
- `GET /tasks/{id}` - Get task status
- `GET /tasks/{id}/result` - Get result
- `DELETE /tasks/{id}` - Cancel task
- `GET /tasks` - List tasks

**System**:
- `GET /health` - Health check
- `GET /info` - Service info (version, available agents)
- `POST /webhooks/test` - Test webhook delivery

### Response Formats

**Synchronous Success**:
```json
{
  "status": "success",
  "agent": "research",
  "markdown": "# Note content...",
  "metadata": {
    "tokens_used": 1234,
    "duration_ms": 5678,
    "model": "gpt-4"
  }
}
```

**Async Task Submission**:
```json
{
  "task_id": "uuid",
  "status": "submitted",
  "status_url": "/tasks/uuid"
}
```

**Error Response**:
```json
{
  "error": "Error message",
  "code": "RATE_LIMIT_EXCEEDED",
  "details": {}
}
```

## Future Feature Ideas

- **Batch Processing**: Submit multiple tasks at once
- **Note Enhancement**: Improve existing notes with AI
- **Scheduled Tasks**: Recurring research or generation
- **Custom Tools**: User-defined agno tools
- **Vector Search**: Semantic search across generated notes
- **Multi-Vault**: Support for multiple Obsidian vaults
- **Streaming**: Real-time streaming of agent outputs
- **Playground UI**: Web interface for testing agents
