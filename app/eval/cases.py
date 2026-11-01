"""
Golden questions for the support agent.

Each case names:
  expected_tools     — tools the agent must call (extras do not fail)
  expected_sources   — at least one of these files must appear in chunks
                       (empty = skip retrieval; used for order-only cases)
  expected_sections  — at least one of these heading names must appear
                       (optional; checks structure-aware ingest)
  must_contain       — every string must appear in the answer (AND)
  must_contain_any   — at least one string must appear (OR)
  expected_order_id  — if set, get_order_by_id must be called with this id

Facts are copied from data/policies/*.md and scripts/seed_orders.py.
If you change a policy file, change the matching case here too.

Order cases belong to USER-8624C7 (the seed script).
"""

EVAL_USER_ID = "USER-8624C7"

CASES = [
    {
        "id": "refund-processing",
        "question": "How long does a refund take?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["refund.md", "cancellation.md"],
        "expected_sections": ["Refund window", "Refund after cancellation"],
        "must_contain": ["5-7"],
    },
    {
        "id": "refund-method",
        "question": "Where is a refund sent?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["refund.md", "cancellation.md"],
        "expected_sections": ["Payment method", "Refund after cancellation"],
        "must_contain": ["original payment"],
    },
    {
        "id": "refund-promo",
        "question": "Can I get a full refund on a promotional discount?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["refund.md"],
        "expected_sections": ["Promotional discounts"],
        "must_contain": ["non-refundable"],
    },
    {
        "id": "refund-window",
        "question": "What is the refund window?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["refund.md", "cancellation.md"],
        "expected_sections": ["Refund window", "Refund after cancellation"],
        "must_contain": ["5-7"],
    },
    {
        "id": "return-window",
        "question": "How long do I have to return a product?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["return.md"],
        "expected_sections": ["Return window"],
        "must_contain": ["7 days"],
    },
    {
        "id": "return-excluded",
        "question": "Are all products eligible for return?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["return.md"],
        "expected_sections": ["Excluded products"],
        "must_contain": ["excluded"],
    },
    {
        "id": "return-paraphrase",
        "question": "I want to send the shoes back. What is the time limit?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["return.md"],
        "expected_sections": ["Return window"],
        "must_contain": ["7 days"],
    },
    {
        "id": "cancel-before-ship",
        "question": "When can I cancel an order?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["cancellation.md"],
        "expected_sections": ["Cancel before shipment"],
        "must_contain_any": ["before", "not shipped"],
    },
    {
        "id": "cancel-after-ship",
        "question": "Can I cancel an order after it has shipped?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["cancellation.md"],
        "expected_sections": ["After shipment"],
        "must_contain_any": ["cannot", "can't", "already been shipped"],
    },
    {
        "id": "cancel-custom",
        "question": "Are there extra rules for cancelling a customized product?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["cancellation.md"],
        "expected_sections": ["Customized products"],
        "must_contain": ["customized"],
    },
    {
        "id": "delivery-time",
        "question": "How long does standard delivery take?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["delivery.md"],
        "expected_sections": ["Delivery window"],
        "must_contain": ["3-7"],
    },
    {
        "id": "delivery-track",
        "question": "How do I check my delivery status?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["delivery.md"],
        "expected_sections": ["Order tracking"],
        "must_contain": ["tracking"],
    },
    {
        "id": "delivery-location",
        "question": "Does delivery time depend on where I live?",
        "expected_tools": ["search_policy"],
        "expected_sources": ["delivery.md"],
        "expected_sections": ["Location and availability"],
        "must_contain": ["location"],
    },
    {
        "id": "today-orders",
        "question": "What did I order today?",
        "expected_tools": ["get_today_orders"],
        "expected_sources": [],
        "must_contain_any": ["MacBook", "iPhone"],
    },
    {
        "id": "order-1001",
        "question": "What is order ORD-1001?",
        "expected_tools": ["get_order_by_id"],
        "expected_sources": [],
        "expected_order_id": "ORD-1001",
        "must_contain": ["MacBook"],
    },
    {
        "id": "order-1002",
        "question": "Tell me about ORD-1002.",
        "expected_tools": ["get_order_by_id"],
        "expected_sources": [],
        "expected_order_id": "ORD-1002",
        "must_contain": ["iPhone"],
    },
    {
        "id": "order-1003",
        "question": "What is the status of ORD-1003?",
        "expected_tools": ["get_order_by_id"],
        "expected_sources": [],
        "expected_order_id": "ORD-1003",
        "must_contain_any": ["CANCELLED", "canceled", "Headphones"],
    },
    {
        "id": "cancel-1002-refund",
        "question": "Can I cancel ORD-1002 and get a refund?",
        "expected_tools": ["get_order_by_id", "search_policy"],
        "expected_sources": ["cancellation.md"],
        "expected_sections": ["After shipment", "Cancel before shipment"],
        "expected_order_id": "ORD-1002",
        "must_contain_any": ["shipped", "cannot", "can't"],
    },
    {
        "id": "refund-1001",
        "question": "ORD-1001 was cancelled. When will I get my money back?",
        "expected_tools": ["get_order_by_id", "search_policy"],
        "expected_sources": ["refund.md", "cancellation.md"],
        "expected_sections": ["Refund window", "Refund after cancellation"],
        "expected_order_id": "ORD-1001",
        "must_contain": ["5-7"],
    },
    {
        "id": "today-and-return",
        "question": "I ordered something today. Can I return it, and what is the time limit?",
        "expected_tools": ["get_today_orders", "search_policy"],
        "expected_sources": ["return.md"],
        "expected_sections": ["Return window"],
        "must_contain": ["7 days"],
    },
]
