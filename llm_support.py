#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qs, unquote, urlparse

import requests

try:
    import anthropic  # type: ignore
except ImportError:
    anthropic = None

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None

try:
    import google.auth  # type: ignore
except ImportError:
    google_auth = None
else:
    google_auth = google.auth


DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "claude-vertex": "claude-sonnet-4-6",
    "kimi": "kimi-k2.5",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]

    def anthropic_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


WEB_SEARCH_TOOL = ToolSpec(
    name="web_search",
    description=(
        "Search the public web for recent OpenROAD, ORFS, physical-design, or provider-context information "
        "that helps choose better parameter settings."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query describing the context or tuning question to investigate.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "minimum": 1,
                "maximum": 8,
                "default": 5,
            },
            "domains": {
                "type": "array",
                "description": "Optional list of domains to prefer or restrict in the query.",
                "items": {"type": "string"},
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)

OPENALEX_TOOL = ToolSpec(
    name="openalex_lookup",
    description=(
        "Look up scholarly papers and metadata from OpenAlex for OpenROAD, Bayesian optimization, "
        "placement, routing, CTS, timing, or design-specific research context."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Paper search query.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of works to return.",
                "minimum": 1,
                "maximum": 8,
                "default": 5,
            },
            "year_from": {
                "type": "integer",
                "description": "Optional lower bound for publication year.",
                "minimum": 1950,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    tool_trace: List[Dict[str, Any]]


class ContextToolExecutor:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": os.environ.get(
                    "ORFS_AGENT_WEB_USER_AGENT",
                    "ORFS-Agent/0.1 (+https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts)",
                )
            }
        )
        self.timeout = float(os.environ.get("ORFS_AGENT_TOOL_TIMEOUT", "20"))

    def execute(self, name: str, arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(arguments or {})
        if name == WEB_SEARCH_TOOL.name:
            return self.web_search(
                query=str(payload.get("query", "")).strip(),
                max_results=int(payload.get("max_results", 5)),
                domains=payload.get("domains") or [],
            )
        if name in (OPENALEX_TOOL.name, "semantic_scholar_lookup"):
            return self.openalex_lookup(
                query=str(payload.get("query", "")).strip(),
                max_results=int(payload.get("max_results", 5)),
                year_from=payload.get("year_from"),
            )
        return {"error": f"Unknown tool: {name}"}

    def web_search(self, query: str, max_results: int = 5, domains: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        if not query:
            return {"error": "query is required", "results": []}
        provider = os.environ.get("ORFS_AGENT_WEB_SEARCH_PROVIDER", "duckduckgo").strip().lower()
        if provider == "brave":
            return self._brave_search(query=query, max_results=max_results, domains=domains or [])
        return self._duckduckgo_search(query=query, max_results=max_results, domains=domains or [])

    def _duckduckgo_search(self, query: str, max_results: int, domains: Sequence[str]) -> Dict[str, Any]:
        scoped_query = query
        if domains:
            scope = " OR ".join(f"site:{domain}" for domain in domains if domain)
            if scope:
                scoped_query = f"({scope}) {query}"
        try:
            response = self.session.get(
                "https://html.duckduckgo.com/html/",
                params={"q": scoped_query},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as error:
            return {
                "provider": "duckduckgo",
                "query": query,
                "results": [],
                "error": str(error),
            }

        html = response.text
        results: List[Dict[str, Any]] = []
        anchor_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            flags=re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
            flags=re.DOTALL | re.IGNORECASE,
        )
        for match in anchor_pattern.finditer(html):
            raw_url = match.group(1)
            title = self._strip_html(match.group(2))
            snippet_match = snippet_pattern.search(html, match.end(), min(len(html), match.end() + 2500))
            snippet = ""
            if snippet_match:
                snippet = self._strip_html(snippet_match.group(1) or snippet_match.group(2) or "")
            results.append(
                {
                    "title": title,
                    "url": self._normalize_duckduckgo_url(raw_url),
                    "snippet": self._truncate_text(snippet, 320),
                }
            )
            if len(results) >= max(1, min(max_results, 8)):
                break
        return {
            "provider": "duckduckgo",
            "query": query,
            "results": results,
        }

    def _brave_search(self, query: str, max_results: int, domains: Sequence[str]) -> Dict[str, Any]:
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return {
                "provider": "brave",
                "query": query,
                "results": [],
                "error": "BRAVE_SEARCH_API_KEY is not set",
            }
        scoped_query = query
        if domains:
            scope = " OR ".join(f"site:{domain}" for domain in domains if domain)
            if scope:
                scoped_query = f"({scope}) {query}"
        try:
            response = self.session.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": scoped_query, "count": max(1, min(max_results, 8))},
                headers={"X-Subscription-Token": api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as error:
            return {
                "provider": "brave",
                "query": query,
                "results": [],
                "error": str(error),
            }
        results = []
        for item in (data.get("web") or {}).get("results", [])[: max(1, min(max_results, 8))]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": self._truncate_text(item.get("description", "") or "", 320),
                }
            )
        return {
            "provider": "brave",
            "query": query,
            "results": results,
        }

    def openalex_lookup(
        self,
        query: str,
        max_results: int = 5,
        year_from: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not query:
            return {"error": "query is required", "works": []}
        api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
        params: Dict[str, Any] = {
            "search": query,
            "per-page": max(1, min(max_results, 8)),
        }
        if api_key:
            params["api_key"] = api_key
        try:
            response = self.session.get(
                "https://api.openalex.org/works",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as error:
            return {
                "provider": "openalex",
                "query": query,
                "works": [],
                "error": str(error),
            }

        works = []
        for item in data.get("results", []):
            year = item.get("publication_year")
            if year_from is not None:
                try:
                    if year is None or int(year) < int(year_from):
                        continue
                except (TypeError, ValueError):
                    continue
            authors = []
            for authorship in item.get("authorships", [])[:8]:
                author = authorship.get("author") or {}
                name = author.get("display_name")
                if name:
                    authors.append(name)
            primary_location = item.get("primary_location") or {}
            source = primary_location.get("source") or {}
            works.append(
                {
                    "title": item.get("display_name", ""),
                    "year": year,
                    "venue": source.get("display_name"),
                    "citationCount": item.get("cited_by_count"),
                    "authors": authors,
                    "url": item.get("id") or item.get("doi") or (primary_location.get("landing_page_url")),
                    "abstract": "",
                    "ids": item.get("ids") or {},
                }
            )
            if len(works) >= max(1, min(max_results, 8)):
                break
        return {
            "provider": "openalex",
            "query": query,
            "works": works,
        }

    def _normalize_duckduckgo_url(self, raw_url: str) -> str:
        url = raw_url.strip()
        if url.startswith("//"):
            url = f"https:{url}"
        parsed = urlparse(url)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
            target = parse_qs(parsed.query).get("uddg", [])
            if target:
                return unquote(target[0])
        return url

    def _strip_html(self, text: str) -> str:
        collapsed = re.sub(r"<[^>]+>", " ", unescape(text))
        return re.sub(r"\s+", " ", collapsed).strip()

    def _truncate_text(self, text: str, max_chars: int) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."


class ToolCallingLLM:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None) -> None:
        self.provider = self._normalize_provider(
            provider
            or os.environ.get("ORFS_AGENT_LLM_PROVIDER")
            or self._autodetect_provider()
        )
        self.model = model or os.environ.get("ORFS_AGENT_MODEL") or DEFAULT_MODELS.get(self.provider, "")
        self.max_tokens = int(os.environ.get("ORFS_AGENT_MAX_TOKENS", "3000"))
        self.max_tool_roundtrips = int(os.environ.get("ORFS_AGENT_MAX_TOOL_ROUNDS", "6"))
        self.context_tools_enabled = os.environ.get("ORFS_AGENT_ENABLE_CONTEXT_TOOLS", "1").strip().lower() not in {"0", "false", "no", "off"}
        self.tool_executor = ContextToolExecutor()
        self.tool_specs = [WEB_SEARCH_TOOL, OPENALEX_TOOL] if self.context_tools_enabled else []

    def external_tooling_enabled(self) -> bool:
        return bool(self.tool_specs) and self.max_tool_roundtrips > 0

    def provider_label(self) -> str:
        if self.model:
            return f"{self.provider}:{self.model}"
        return self.provider

    def availability_reason(self) -> Optional[str]:
        if self.provider == "none":
            return "No LLM provider configured. Set ORFS_AGENT_LLM_PROVIDER to anthropic, claude-vertex, or kimi."
        if self.provider == "anthropic":
            if anthropic is None:
                return "The anthropic package is not installed."
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return "ANTHROPIC_API_KEY is not set."
            return None
        if self.provider == "claude-vertex":
            if anthropic is None:
                return "The anthropic package is not installed."
            if not hasattr(anthropic, "AnthropicVertex"):
                return "Installed anthropic package does not expose AnthropicVertex."
            if not self._vertex_project_id():
                return "Set ORFS_AGENT_VERTEX_PROJECT_ID or configure Application Default Credentials with a project."
            if not self._vertex_region():
                return "Set ORFS_AGENT_VERTEX_REGION or GOOGLE_CLOUD_LOCATION for Claude on Vertex AI."
            return None
        if self.provider == "kimi":
            if OpenAI is None:
                return "The openai package is not installed."
            if not os.environ.get("MOONSHOT_API_KEY"):
                return "MOONSHOT_API_KEY is not set."
            return None
        return f"Unsupported LLM provider: {self.provider}"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        if self.availability_reason() is not None:
            return None
        if self.provider == "anthropic":
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            return self._generate_with_anthropic(client, prompt=prompt, system_prompt=system_prompt)
        if self.provider == "claude-vertex":
            client = anthropic.AnthropicVertex(
                project_id=self._vertex_project_id(),
                region=self._vertex_region(),
            )
            return self._generate_with_anthropic(client, prompt=prompt, system_prompt=system_prompt)
        if self.provider == "kimi":
            client = OpenAI(
                api_key=os.environ["MOONSHOT_API_KEY"],
                base_url=os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"),
            )
            return self._generate_with_openai(client, prompt=prompt, system_prompt=system_prompt)
        return None

    def _generate_with_anthropic(self, client: Any, prompt: str, system_prompt: Optional[str]) -> Optional[LLMResponse]:
        messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
        tool_trace: List[Dict[str, Any]] = []
        for _ in range(self.max_tool_roundtrips):
            request: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
            }
            if self.tool_specs:
                request["tools"] = [tool.anthropic_schema() for tool in self.tool_specs]
            if system_prompt:
                request["system"] = system_prompt
            response = client.messages.create(**request)
            assistant_blocks: List[Dict[str, Any]] = []
            text_blocks: List[str] = []
            tool_results: List[Dict[str, Any]] = []
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    text = getattr(block, "text", "")
                    assistant_blocks.append({"type": "text", "text": text})
                    if text:
                        text_blocks.append(text)
                    continue
                if block_type != "tool_use":
                    continue
                tool_name = getattr(block, "name", "")
                tool_input = dict(getattr(block, "input", {}) or {})
                tool_result = self.tool_executor.execute(tool_name, tool_input)
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": getattr(block, "id", ""),
                        "name": tool_name,
                        "input": tool_input,
                    }
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": getattr(block, "id", ""),
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
                tool_trace.append(self._tool_trace_entry(tool_name, tool_input, tool_result))
            messages.append({"role": "assistant", "content": assistant_blocks})
            if not tool_results:
                return LLMResponse(
                    text="\n".join(text_blocks).strip(),
                    provider=self.provider,
                    model=self.model,
                    tool_trace=tool_trace,
                )
            messages.append({"role": "user", "content": tool_results})
        return LLMResponse(text="", provider=self.provider, model=self.model, tool_trace=tool_trace)

    def _generate_with_openai(self, client: Any, prompt: str, system_prompt: Optional[str]) -> Optional[LLMResponse]:
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        tool_trace: List[Dict[str, Any]] = []
        for _ in range(self.max_tool_roundtrips):
            request: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": 0.6,
                "extra_body": {"thinking": {"type": "disabled"}},
            }
            if self.tool_specs:
                request["tools"] = [tool.openai_schema() for tool in self.tool_specs]
                request["tool_choice"] = "auto"
            response = client.chat.completions.create(**request)
            message = response.choices[0].message
            assistant_message: Dict[str, Any] = {
                "role": "assistant",
                "content": self._message_text(message),
            }
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                assistant_message["tool_calls"] = []
                for call in tool_calls:
                    assistant_message["tool_calls"].append(
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                    )
            messages.append(assistant_message)
            if not tool_calls:
                return LLMResponse(
                    text=self._message_text(message).strip(),
                    provider=self.provider,
                    model=self.model,
                    tool_trace=tool_trace,
                )
            for call in tool_calls:
                tool_name = call.function.name
                try:
                    tool_input = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_input = {}
                tool_result = self.tool_executor.execute(tool_name, tool_input)
                tool_trace.append(self._tool_trace_entry(tool_name, tool_input, tool_result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )
        return LLMResponse(text="", provider=self.provider, model=self.model, tool_trace=tool_trace)

    def _tool_trace_entry(self, tool_name: str, tool_input: Dict[str, Any], tool_result: Dict[str, Any]) -> Dict[str, Any]:
        if "results" in tool_result:
            count = len(tool_result.get("results") or [])
        elif "works" in tool_result:
            count = len(tool_result.get("works") or [])
        elif "papers" in tool_result:
            count = len(tool_result.get("papers") or [])
        else:
            count = 0
        return {
            "name": tool_name,
            "arguments": tool_input,
            "provider": tool_result.get("provider"),
            "count": count,
            "error": tool_result.get("error"),
        }

    def _normalize_provider(self, provider: Optional[str]) -> str:
        normalized = (provider or "none").strip().lower().replace("_", "-")
        aliases = {
            "claude": "anthropic",
            "anthropic-direct": "anthropic",
            "vertex": "claude-vertex",
            "claudevertex": "claude-vertex",
            "anthropic-vertex": "claude-vertex",
            "moonshot": "kimi",
            "moonshotai": "kimi",
            "kimi-k2.5": "kimi",
        }
        return aliases.get(normalized, normalized)

    def _autodetect_provider(self) -> str:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.environ.get("MOONSHOT_API_KEY"):
            return "kimi"
        return "none"

    def _vertex_project_id(self) -> Optional[str]:
        project_id = (
            os.environ.get("ORFS_AGENT_VERTEX_PROJECT_ID")
            or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCLOUD_PROJECT")
        )
        if project_id:
            return project_id
        if google_auth is None:
            return None
        try:
            _, detected_project = google_auth.default()
        except Exception:
            return None
        return detected_project

    def _vertex_region(self) -> Optional[str]:
        return (
            os.environ.get("ORFS_AGENT_VERTEX_REGION")
            or os.environ.get("ANTHROPIC_VERTEX_REGION")
            or os.environ.get("GOOGLE_CLOUD_LOCATION")
            or os.environ.get("VERTEX_REGION")
        )

    def _message_text(self, message: Any) -> str:
        content = getattr(message, "content", None)
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                    continue
                text = getattr(part, "text", None)
                if text is not None:
                    parts.append(text)
                    continue
                if isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
            return "\n".join(part for part in parts if part)
        return str(content)
