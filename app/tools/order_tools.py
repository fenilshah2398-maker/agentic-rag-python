"""
Order tools — structured MongoDB access for the agent.

These are the agent's "hands" for order facts (not RAG).
The LLM never talks to MongoDB directly; ToolNode calls these functions.

Security pattern:
  user_id uses InjectedState → taken from graph state (API payload),
  NOT chosen by the LLM. Prevents cross-user data leaks / invented ids.
"""

from datetime import datetime, timezone
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from app.db.mongo import orders_collection


@tool
async def get_today_orders(
    user_id: Annotated[str, InjectedState("user_id")],
):
    """
    Get the authenticated user's orders created today.

    Docstring is important: the LLM reads it as the tool description
    when deciding whether to call this tool.

    Note: user_id is InjectedState — hidden from the tool schema the model sees.
    ToolNode fills it from state["user_id"] at runtime.
    """

    # Use UTC so "today" matches how seed_orders.py stores order_date
    now = datetime.now(timezone.utc)

    # Midnight UTC of the current day
    start_of_day = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    # Filter: same user AND order_date within [start_of_day, now)
    # Orders from yesterday (e.g. ORD-1003 in seed data) are intentionally excluded
    cursor = orders_collection.find(
        {
            "user_id": user_id,
            "order_date": {
                "$gte": start_of_day,
                "$lt": now,
            },
        }
    )

    orders = await cursor.to_list(
        length=100
    )

    # Mongo ObjectId is not JSON-friendly for LLM tool results — strip it
    for order in orders:
        order.pop("_id", None)

    return orders


@tool
async def get_order_by_id(
    order_id: str,
    user_id: Annotated[str, InjectedState("user_id")],
):
    """
    Get one order belonging to the authenticated user.

    order_id is a normal tool argument — the LLM may supply it
    (e.g. from the user saying "ORD-1001").

    user_id is still injected from state for tenancy safety.
    Both user_id AND order_id must match, so user A cannot fetch user B's order
    even if they guess an order_id.
    """

    order = await orders_collection.find_one(
        {
            "user_id": user_id,
            "order_id": order_id,
        }
    )

    if not order:
        # Return a structured error the LLM can explain to the user
        return {
            "error": "Order not found"
        }

    order.pop("_id", None)

    return order
