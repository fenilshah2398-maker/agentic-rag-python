"""
AgentState — shared memory that travels through every LangGraph node.

Why state exists:
  Nodes (agent, tools) are separate functions. They need a common bag of data
  so the LLM can see prior tool results, and tools can see user_id.

Think of state as the "backpack" carried from START → END.
"""

from typing import Annotated, TypedDict

# add_messages = reducer that APPENDS new messages to the list
# Without it, returning {"messages": [x]} would REPLACE the entire history
# and break the tool loop (HumanMessage / AIMessage would disappear).
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Shape of graph state.

    messages:
      Conversation transcript in LangChain message objects:
        - HumanMessage  → user question (from FastAPI)
        - AIMessage     → LLM text and/or tool_calls
        - ToolMessage   → result from ToolNode after a tool runs
      Annotated[..., add_messages] tells LangGraph HOW to merge updates.

    user_id:
      Authenticated user from the API payload (trusted server value).
      Injected into order tools via InjectedState("user_id") so the LLM
      cannot invent a different id (e.g. user_1234).
    """

    messages: Annotated[list, add_messages]

    user_id: str
