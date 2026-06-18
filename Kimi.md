**Endpoints and compatibility.**
Moonshot exposes an OpenAI-compatible API at `api.moonshot.ai` with base path `/v1`; a regional `api.moonshot.cn` endpoint is also documented. In our agent loop, the two most relevant surfaces are `/v1/chat/completions` and the file-extraction workflow (`/v1/files` plus `/content`) used for long-context grounding.

**Parameter quirks relative to OpenAI ChatCompletions.**
Moonshot documents two practical differences that matter for sampling logic: (i) the temperature range is `[0, 1]`, and (ii) when temperature is set to `0` or very close to `0`, the API only supports returning a single choice and will error if `n > 1`. We keep `n=1` for deterministic settings and emit multiple proposals within one structured completion.

**Tool calling constraints.**
Kimi follows the OpenAI-style `tools` interface, with tool definitions expressed as a JSON-Schema subset. Two constraints we explicitly enforce in our adapter are: (i) tool names must follow the documented naming rule: start with a letter or underscore, then up to 63 characters from letters, digits, hyphen, or underscore; and (ii) the number of tools in a single request is bounded, with Moonshot documenting a maximum of 128.

**Structured outputs: JSON Mode and Partial Mode.**
For strict parsing, Kimi exposes a JSON Mode via `response_format={"type":"json_object"}`. It supports a “Partial Mode” (`"partial": true`) for output prefilling; Moonshot warns not to combine Partial Mode with JSON Mode.

**Thinking traces.**
For Kimi thinking-enabled models, such as `kimi-k2-thinking` and `kimi-k2.5`, Moonshot returns an explicit reasoning trace in a separate `reasoning_content` field. When using the OpenAI SDK, this field is not part of the stock message type and must be accessed via attribute checks, such as `hasattr` or `getattr`. In streaming mode, `reasoning_content` appears before `content`, and Moonshot notes that the combined token count of `reasoning_content` and `content` is bounded by `max_tokens`; we exploit this property when budgeting output length.

**Reproducibility.**
