"""
Query processing module.

Feature 6.2: Query Rewriting
"""
from services.api.modules.query.rewriter import (
    QueryRewriter,
    QueryRewriteResult,
    QueryRewriteSettings,
    build_rewrite_prompt,
    choose_rewrite_strategy,
    get_recent_chat_history,
    get_query_rewrite_settings,
)

__all__ = [
    "QueryRewriter",
    "QueryRewriteResult",
    "QueryRewriteSettings",
    "build_rewrite_prompt",
    "choose_rewrite_strategy",
    "get_recent_chat_history",
    "get_query_rewrite_settings",
]
