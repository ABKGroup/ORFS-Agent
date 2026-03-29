# ORFS-Agent `env.md`

Human-fill template for the journal-extension provider stack in `ORFS-Agent-clean/`.

## Rules

- Do not commit real secrets.
- Pick one LLM provider at a time: `anthropic`, `claude-vertex`, or `kimi`.
- DuckDuckGo search works with no key.
- Brave and OpenAlex keys are optional but useful.

## 1) Direct Claude via Anthropic

```bash
export ORFS_AGENT_LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="PASTE_YOUR_ANTHROPIC_API_KEY_HERE"

# Optional explicit model override
# export ORFS_AGENT_MODEL="claude-sonnet-4-6"
```

Where to get it:

- Anthropic console API keys: `https://console.anthropic.com/settings/keys`
- Anthropic docs: `https://docs.anthropic.com/`

## 2) Claude on Vertex AI

```bash
export ORFS_AGENT_LLM_PROVIDER="claude-vertex"
export ORFS_AGENT_VERTEX_PROJECT_ID="YOUR_GCP_PROJECT_ID"
export ORFS_AGENT_VERTEX_REGION="YOUR_VERTEX_REGION"

# Strongly recommended if the default model is not exposed in your region.
# export ORFS_AGENT_MODEL="YOUR_VERTEX_CLAUDE_MODEL_ID"

# Choose one ADC path:
# gcloud auth application-default login
# or
# export GOOGLE_APPLICATION_CREDENTIALS="/ABSOLUTE/PATH/TO/adc-or-service-account.json"
```

Where to get it:

- Vertex Claude overview: `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude`
- Vertex Claude usage / regions / model IDs: `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/use-claude`
- ADC overview: `https://docs.cloud.google.com/docs/authentication/provide-credentials-adc`

Checklist:

- [ ] enable `aiplatform.googleapis.com`
- [ ] confirm IAM permission to call Vertex AI
- [ ] set ADC via `gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`
- [ ] choose a region where the Claude model is available

Accepted fallback variables in code:

```bash
export ANTHROPIC_VERTEX_PROJECT_ID="YOUR_GCP_PROJECT_ID"
export GOOGLE_CLOUD_PROJECT="YOUR_GCP_PROJECT_ID"
export GCLOUD_PROJECT="YOUR_GCP_PROJECT_ID"

export ANTHROPIC_VERTEX_REGION="YOUR_VERTEX_REGION"
export GOOGLE_CLOUD_LOCATION="YOUR_VERTEX_REGION"
export VERTEX_REGION="YOUR_VERTEX_REGION"
```

## 3) Kimi K2.5 via Moonshot

```bash
export ORFS_AGENT_LLM_PROVIDER="kimi"
export MOONSHOT_API_KEY="PASTE_YOUR_MOONSHOT_API_KEY_HERE"

# Optional
# export MOONSHOT_BASE_URL="https://api.moonshot.ai/v1"
# export ORFS_AGENT_MODEL="kimi-k2.5"
```

Where to get it:

- Moonshot platform: `https://platform.moonshot.ai/`
- Kimi API quickstart: `https://platform.moonshot.ai/docs/guide/start-using-kimi-api`
- Kimi K2.5 quickstart: `https://platform.moonshot.ai/docs/guide/kimi-k2-5-quickstart`
- Chat API reference: `https://platform.moonshot.ai/docs/api/chat`

## 4) Web Search

Default, no key required:

```bash
export ORFS_AGENT_WEB_SEARCH_PROVIDER="duckduckgo"
```

Optional Brave Search:

```bash
export ORFS_AGENT_WEB_SEARCH_PROVIDER="brave"
export BRAVE_SEARCH_API_KEY="PASTE_YOUR_BRAVE_SEARCH_API_KEY_HERE"
```

Where to get it:

- Brave Search API overview: `https://brave.com/search/api/`
- Brave quickstart: `https://api-dashboard.search.brave.com/documentation/quickstart`
- Brave auth docs: `https://api-dashboard.search.brave.com/documentation/guides/authentication`

## 5) OpenAlex Lookup

```bash
export OPENALEX_API_KEY="PASTE_YOUR_OPENALEX_API_KEY_HERE"
```

Where to get it:

- OpenAlex docs home: `https://docs.openalex.org/`
- OpenAlex API overview: `https://docs.openalex.org/api`
- OpenAlex works endpoint: `https://docs.openalex.org/api-entities/works`

Notes:

- `llm_support.py` calls `https://api.openalex.org/works`
- if `OPENALEX_API_KEY` is set, it is sent as the `api_key` query parameter
- anonymous access may work but is commonly rate-limited

## 6) Optional Runtime Knobs

```bash
# Override the selected provider's model ID
# export ORFS_AGENT_MODEL="..."

# Disable external context tools entirely
# export ORFS_AGENT_ENABLE_CONTEXT_TOOLS="0"

# Cap tool-call loops per LLM turn
# export ORFS_AGENT_MAX_TOOL_ROUNDS="6"

# Max output tokens per turn
# export ORFS_AGENT_MAX_TOKENS="3000"

# HTTP timeout for web / OpenAlex calls
# export ORFS_AGENT_TOOL_TIMEOUT="20"
```

## 7) Minimal Templates

### Direct Claude

```bash
export ORFS_AGENT_LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY=""
```

### Claude on Vertex

```bash
export ORFS_AGENT_LLM_PROVIDER="claude-vertex"
export ORFS_AGENT_VERTEX_PROJECT_ID=""
export ORFS_AGENT_VERTEX_REGION=""
# export ORFS_AGENT_MODEL=""
# export GOOGLE_APPLICATION_CREDENTIALS="/abs/path/to/credentials.json"
```

### Kimi K2.5

```bash
export ORFS_AGENT_LLM_PROVIDER="kimi"
export MOONSHOT_API_KEY=""
# export MOONSHOT_BASE_URL="https://api.moonshot.ai/v1"
# export ORFS_AGENT_MODEL="kimi-k2.5"
```

### Optional Tools

```bash
# export ORFS_AGENT_WEB_SEARCH_PROVIDER="brave"
# export BRAVE_SEARCH_API_KEY=""
# export OPENALEX_API_KEY=""
```
