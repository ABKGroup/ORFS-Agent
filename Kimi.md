\noindent\textbf{Endpoints and compatibility.}
Moonshot exposes an OpenAI-compatible API at \texttt{api.moonshot.ai} (base path
\texttt{/v1}; a regional \texttt{api.moonshot.cn} endpoint is also documented). In our
agent loop, the two most relevant surfaces are \texttt{/v1/chat/completions} and the
file-extraction workflow (\texttt{/v1/files} plus \texttt{/content}) used for
long-context grounding.

\noindent\textbf{Parameter quirks relative to OpenAI ChatCompletions.}
Moonshot documents two practical differences that matter for sampling logic:
(i) the temperature range is $[0,1]$, and (ii) when temperature is set to $0$ (or very
close to $0$), the API only supports returning a single choice, and will error if
\texttt{n>1}. We keep \texttt{n=1} for deterministic settings and emit
multiple proposals within one structured completion.

\noindent\textbf{Tool calling constraints.}
Kimi follows the OpenAI-style \texttt{tools} interface, with tool definitions expressed
as a JSON-Schema subset. Two constraints we explicitly enforce in our adapter are:
(i) tool names must follow the documented naming rule (start with a letter or
underscore; then up to 63 characters from letters, digits, hyphen, or underscore),
and (ii) the number of tools in a single request is bounded (Moonshot documents a
maximum of 128).

\noindent\textbf{Structured outputs: JSON Mode and Partial Mode.}
For strict parsing, Kimi exposes a JSON Mode via
\texttt{response\_format=\{"type":"json\_object"\}}. It supports a
``Partial Mode'' (\texttt{"partial": true}) for output prefilling; Moonshot warns not
to combine Partial Mode with JSON Mode.

\noindent\textbf{Thinking traces.}
For Kimi thinking-enabled models (e.g., \texttt{kimi-k2-\allowbreak thinking} and \texttt{kimi-k2.5}), Moonshot
returns an explicit reasoning trace in a separate \texttt{reasoning\_\allowbreak content} field.
When using the OpenAI SDK, this field is not part of the stock message type and must
be accessed via attribute checks (e.g., \texttt{hasattr}/\texttt{getattr}). In streaming
mode, \texttt{reasoning\_\allowbreak content} appears before \texttt{content}, and Moonshot notes
that the combined token count of \texttt{reasoning\_\allowbreak content} and \texttt{content} is
bounded by \texttt{max\_tokens}; we exploit this property when budgeting output length.
 

\noindent\textbf{Reproducibility.}
