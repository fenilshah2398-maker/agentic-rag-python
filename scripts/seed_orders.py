"""
One-time / repeatable script: seed demo orders into MongoDB Atlas.

Run from project root:
  python -m scripts.seed_orders

What it does:
  1. Connect using settings from .env (Atlas URI + database)
  2. Wipe existing docs in `orders` (delete_many)
  3. Insert three demo rows for USER-001

Date design (important for get_today_orders):
  ORD-1001 / ORD-1002 → today (hours ago)   → returned by "today" tool
  ORD-1003            → yesterday           → excluded by "today" filter
"""

import asyncio
from datetime import datetime, timezone, timedelta

from pymongo import AsyncMongoClient

from app.config import settings


async def seed():
    """Insert deterministic demo orders for testing the agent."""

    client = AsyncMongoClient(settings.mongodb_uri)

    db = client[settings.mongodb_database]

    orders = db["orders"]

    now = datetime.now(timezone.utc)

    data = [
        {
            "order_id": "ORD-1001",
            "user_id": "USER-8624C7",
            "product": "MacBook Pro",
            "amount": 180000,
            "status": "DELIVERED",
            "order_date": now - timedelta(hours=2),
        },
        {
            "order_id": "ORD-1002",
            "user_id": "USER-8624C7",
            "product": "iPhone 17",
            "amount": 90000,
            "status": "SHIPPED",
            "order_date": now - timedelta(hours=1),
        },
        {
            "order_id": "ORD-1003",
            "user_id": "USER-8624C7",
            "product": "Headphones",
            "amount": 12000,
            "status": "CANCELLED",
            # Yesterday → will NOT appear in get_today_orders
            "order_date": now - timedelta(days=1),
        },
    ]

    # Clean slate so re-running the script does not stack duplicates
    await orders.delete_many({})

    await orders.insert_many(data)

    print("Orders inserted")

    await client.close()


if __name__ == "__main__":
    # asyncio.run bridges sync CLI entry → async seed()
    asyncio.run(seed())
