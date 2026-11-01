// Short RAG evidence under an assistant bubble.
//
// The server keeps the full chunk text in its log. The page only gets
// source, score, and a one-line preview so you can see *why* the
// answer was produced without opening the terminal.

function formatTool(tool) {
  const args = tool.args && Object.keys(tool.args).length > 0
    ? ` ${JSON.stringify(tool.args)}`
    : ""
  return `${tool.name}${args}`
}

export function TracePanel({ trace }) {
  if (!trace) return null

  const chunks = trace.chunks || []
  const tools = trace.tools || []
  const latency = trace.latency_ms || {}
  const tokens = trace.tokens || {}
  const bits = []
  if (chunks.length) bits.push(`${chunks.length} chunks`)
  if (latency.total != null) bits.push(`${latency.total}ms`)
  if (trace.from_cache) bits.push("from cache")

  return (
    <details className="trace" open>
      <summary>Trace{bits.length ? ` · ${bits.join(" · ")}` : ""}</summary>

      <dl className="trace-meta">
        {trace.original_query && trace.search_query && trace.original_query !== trace.search_query && (
          <>
            <dt>Original query</dt>
            <dd>{trace.original_query}</dd>
          </>
        )}
        {trace.search_query && (
          <>
            <dt>Search query</dt>
            <dd>{trace.search_query}</dd>
          </>
        )}
        {trace.abstain && (
          <>
            <dt>Abstain</dt>
            <dd>no supporting policy (best {trace.best_vector ?? "—"})</dd>
          </>
        )}
        <dt>Tools</dt>
        <dd>{tools.length ? tools.map(formatTool).join(" → ") : "none"}</dd>
        <dt>Latency</dt>
        <dd>
          total {latency.total ?? 0}ms
          {` · rewrite ${latency.rewrite ?? 0}ms`}
          {` · retrieve ${latency.retrieve ?? 0}ms`}
          {` · rerank ${latency.rerank ?? 0}ms`}
          {` · llm ${latency.llm ?? 0}ms`}
          {trace.over_budget?.length ? ` · over ${trace.over_budget.join(", ")}` : ""}
        </dd>
        <dt>Tokens</dt>
        <dd>
          in {tokens.input ?? 0}
          {` · out ${tokens.output ?? 0}`}
          {` · total ${tokens.total ?? 0}`}
        </dd>
      </dl>

      {chunks.length > 0 && (
        <ol className="trace-chunks">
          {chunks.map((chunk, index) => (
            <li key={`${chunk.source}-${index}`}>
              <div className="trace-chunk-head">
                <span className="trace-score">
                  {chunk.score == null ? "—" : Number(chunk.score).toFixed(3)}
                </span>
                <span className="trace-source">
                  {[chunk.source || "unknown", chunk.section].filter(Boolean).join(" · ")}
                  {chunk.policy ? ` (${chunk.policy})` : ""}
                </span>
              </div>
              <p>{chunk.preview}</p>
            </li>
          ))}
        </ol>
      )}
    </details>
  )
}
