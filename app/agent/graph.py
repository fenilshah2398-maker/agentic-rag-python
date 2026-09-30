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
"""

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


# ---------------------------------------------------------------------------
# DO step — THIS is the code that runs tools after the LLM names them
# ---------------------------------------------------------------------------
# Example: LLM returns tool_calls=[{name: "get_today_orders", ...}]
# ToolNode finds get_today_orders in `tools`, injects InjectedState fields,
# awaits the function, and stores the result as a ToolMessage in state["messages"].
tool_node = ToolNode(tools)


def should_continue(state):
    """
    DECIDE step — conditional router after every agent_node run.

    Inspects the latest message in state:
      - If it contains tool_calls → go to the "tools" node (DO)
      - Otherwise the LLM produced a final answer → END

    getattr(..., "tool_calls", None) is used because not every message type
    has a tool_calls attribute (e.g. HumanMessage / ToolMessage).
    """

    last_message = state["messages"][-1]

    if getattr(
        last_message,
        "tool_calls",
        None,
    ):
        # Must match a key in the path_map below AND a registered node name
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
