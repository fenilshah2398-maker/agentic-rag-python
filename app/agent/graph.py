"""
LangGraph wiring — the "brain diagram" of the agent.

Mental model (every chat request):

  THINK  → agent_node     (LLM decides: answer OR call tools)
  DECIDE → should_continue (route based on tool_calls)
  DO     → ToolNode       (actually runs Python tools)
  loop   → tools always return to agent until LLM gives a final text answer

Graph shape:

  START ──► agent ──► (conditional)
                        │
              has tool_calls? ──yes──► tools ──► agent (again)
                        │
                        no
                        ▼
                       END

This module only DEFINES the graph. Runtime starts from main.py via graph.ainvoke(...).

Guardrails in this file (code, not prompt):
  - only tools in the allowlist may run
  - the think/tool loop stops after MAX_TOOL_ROUNDS
"""

from langchain_core.messages import ToolMessage
from langgraph.graph import (
    StateGraph,  # builder for a stateful directed graph
    START,       # virtual entry node
    END,         # virtual terminal node
)

# ToolNode = prebuilt executor: reads AIMessage.tool_calls → runs matching @tool → appends ToolMessage
from langgraph.prebuilt import ToolNode

# Shared memory schema for every node (messages + user_id)
from app.agent.state import AgentState

# agent_node = LLM step; tools = list of callable tools registered with the LLM
from app.agent.nodes import (
    agent_node,
    tools,
)


MAX_TOOL_ROUNDS = 4
ALLOWED_TOOLS = {tool.name for tool in tools}


# ---------------------------------------------------------------------------
# DO step — THIS is the code that runs tools after the LLM names them
# ---------------------------------------------------------------------------
# Example: LLM returns tool_calls=[{name: "get_today_orders", ...}]
# ToolNode finds get_today_orders in `tools`, injects InjectedState fields,
# awaits the function, and stores the result as a ToolMessage in state["messages"].
_raw_tool_node = ToolNode(tools)


def _tool_rounds(state) -> int:
    return sum(
        1
        for message in state.get("messages") or []
        if getattr(message, "tool_calls", None)
    )


async def tool_node(state):
    """Run tools, but drop any name that is not on the allowlist."""
    last_message = state["messages"][-1]
    calls = getattr(last_message, "tool_calls", None) or []
    blocked = []
    kept = []
    for call in calls:
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
        call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", "")
        if name not in ALLOWED_TOOLS:
            blocked.append(
                ToolMessage(
                    content="Tool is not allowed.",
                    tool_call_id=call_id,
                    name=name,
                )
            )
        else:
            kept.append(call)

    if not kept:
        return {"messages": blocked}

    if blocked:
        last_message.tool_calls = kept
    result = await _raw_tool_node.ainvoke(state)
    if blocked:
        result = {"messages": blocked + list(result.get("messages") or [])}
    return result


def should_continue(state):
    """
    DECIDE step — conditional router after every agent_node run.

    Inspects the latest message in state:
      - If it contains tool_calls → go to the "tools" node (DO)
      - Otherwise the LLM produced a final answer → END

    After MAX_TOOL_ROUNDS we stop even if the model wants another tool.
    """

    last_message = state["messages"][-1]
    calls = getattr(last_message, "tool_calls", None)

    if calls and _tool_rounds(state) > MAX_TOOL_ROUNDS:
        return END

    if calls:
        return "tools"

    return END


# ---------------------------------------------------------------------------
# Build the graph: every node reads/writes AgentState
# ---------------------------------------------------------------------------
graph_builder = StateGraph(
    AgentState
)


# THINK node — name "agent" is just a label used by edges
graph_builder.add_node(
    "agent",
    agent_node
)

# DO node — name "tools" is the label should_continue returns
graph_builder.add_node(
    "tools",
    tool_node
)


# Always start by thinking (call the LLM first)
graph_builder.add_edge(
    START,
    "agent"
)

# After agent: branch using should_continue
# path_map maps return values of should_continue → next node
graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",  # LLM requested tool(s)
        END: END,          # LLM finished with text only
    },
)

# After tools finish, ALWAYS go back to agent so the LLM can:
#   - call more tools, OR
#   - write the final natural-language answer using tool results
graph_builder.add_edge(
    "tools",
    "agent"
)

# compile() freezes the graph into a runnable object used by FastAPI
graph = graph_builder.compile()
