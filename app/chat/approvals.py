"""
Human approval for a write.

request_cancellation is a *proposal*. It does not change Mongo.
execute_cancellation runs only after the chat page sends Approve.

The model is not allowed to flip an order to CANCELLED on its own.
"""

from datetime import datetime, timezone

from app.db.mongo import orders_collection


async def preview_cancellation(user_id: str, order_id: str) -> dict:
    order = await orders_collection.find_one(
        {"user_id": user_id, "order_id": order_id}
    )
    if not order:
        return {"error": "Order not found", "needs_approval": False}

    return {
        "needs_approval": True,
        "order_id": order["order_id"],
        "product": order.get("product"),
        "status": order.get("status"),
        "message": (
            f"I can cancel {order['order_id']} ({order.get('product')}, "
            f"status {order.get('status')}) if you approve."
        ),
    }


async def execute_cancellation(user_id: str, order_id: str) -> dict:
    order = await orders_collection.find_one(
        {"user_id": user_id, "order_id": order_id}
    )
    if not order:
        return {"ok": False, "error": "Order not found"}
    if order.get("status") == "CANCELLED":
        return {"ok": False, "error": "Order is already cancelled"}
    if order.get("status") in {"SHIPPED", "DELIVERED"}:
        return {
            "ok": False,
            "error": (
                f"{order_id} is {order.get('status')}. "
                "Shipped orders cannot normally be cancelled."
            ),
        }

    await orders_collection.update_one(
        {"user_id": user_id, "order_id": order_id},
        {
            "$set": {
                "status": "CANCELLED",
                "cancelled_at": datetime.now(timezone.utc),
            }
        },
    )
    return {
        "ok": True,
        "order_id": order_id,
        "status": "CANCELLED",
        "product": order.get("product"),
    }
