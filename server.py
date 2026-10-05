import os
import re
from typing import Any

import httpx
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

X_API_BASE = "https://api.x.com/2"
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "").strip()

mcp = MCPServer("X Replies Analyzer")


def _token() -> str:
    if not BEARER_TOKEN:
        raise RuntimeError("X_BEARER_TOKEN is not configured on the server.")
    return BEARER_TOKEN


def _extract_post_id(url_or_id: str) -> str:
    value = url_or_id.strip()
    if re.fullmatch(r"\d{1,19}", value):
        return value
    match = re.search(r"/(?:status|statuses)/(\d{1,19})(?:[/?#]|$)", value)
    if not match:
        raise ValueError("Could not find a numeric X post ID in the supplied URL.")
    return match.group(1)


async def _x_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {_token()}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{X_API_BASE}{path}", headers=headers, params=params)
    if response.status_code >= 400:
        body = response.text[:1200]
        raise RuntimeError(f"X API returned HTTP {response.status_code}: {body}")
    return response.json()


@mcp.tool()
async def get_post(url_or_id: str) -> dict[str, Any]:
    """Read one public X post by URL or numeric post ID."""
    post_id = _extract_post_id(url_or_id)
    params = {
        "tweet.fields": "created_at,author_id,conversation_id,public_metrics,referenced_tweets,lang",
        "expansions": "author_id",
        "user.fields": "name,username,verified,public_metrics",
    }
    payload = await _x_get(f"/tweets/{post_id}", params=params)
    return {"post_id": post_id, "raw": payload}


@mcp.tool()
async def get_replies(
    url_or_id: str,
    limit: int = 100,
    direct_only: bool = False,
    include_authors: bool = True,
) -> dict[str, Any]:
    """Fetch recent replies in the conversation for a public X post.

    Args:
        url_or_id: X post URL or numeric post ID.
        limit: Maximum replies to return (1-200). Default 100.
        direct_only: If true, keep only replies directly to the root post.
        include_authors: Include expanded author objects when available.
    """
    post_id = _extract_post_id(url_or_id)
    limit = max(1, min(int(limit), 200))

    root = await _x_get(
        f"/tweets/{post_id}",
        params={"tweet.fields": "conversation_id,created_at,author_id,public_metrics"},
    )
    conversation_id = root.get("data", {}).get("conversation_id") or post_id

    query = f"conversation_id:{conversation_id} is:reply"
    collected: list[dict[str, Any]] = []
    authors: dict[str, dict[str, Any]] = {}
    next_token: str | None = None

    while len(collected) < limit:
        page_size = min(100, max(10, limit - len(collected)))
        params: dict[str, Any] = {
            "query": query,
            "max_results": page_size,
            "tweet.fields": "created_at,author_id,conversation_id,public_metrics,referenced_tweets,in_reply_to_user_id,lang",
            "sort_order": "recency",
        }
        if include_authors:
            params["expansions"] = "author_id"
            params["user.fields"] = "name,username,verified,public_metrics"
        if next_token:
            params["next_token"] = next_token

        payload = await _x_get("/tweets/search/recent", params=params)

        if include_authors:
            for user in payload.get("includes", {}).get("users", []) or []:
                uid = user.get("id")
                if uid:
                    authors[uid] = user

        page_items = payload.get("data", []) or []
        if not page_items:
            break

        for item in page_items:
            if item.get("id") == post_id:
                continue
            if direct_only:
                refs = item.get("referenced_tweets", []) or []
                parent_ids = [r.get("id") for r in refs if r.get("type") == "replied_to"]
                if post_id not in parent_ids:
                    continue
            collected.append(item)
            if len(collected) >= limit:
                break

        next_token = payload.get("meta", {}).get("next_token")
        if not next_token:
            break

    # de-duplicate while preserving order
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in collected:
        iid = item.get("id")
        if not iid or iid in seen:
            continue
        seen.add(iid)
        row = dict(item)
        if include_authors and item.get("author_id") in authors:
            row["author"] = authors[item["author_id"]]
        deduped.append(row)

    return {
        "root_post_id": post_id,
        "conversation_id": conversation_id,
        "requested_limit": limit,
        "returned_count": len(deduped),
        "direct_only": direct_only,
        "has_more": bool(next_token),
        "replies": deduped,
    }

security = TransportSecuritySettings(
    allowed_hosts=[
        "x-replies-mcp.onrender.com",
        "x-replies-mcp.onrender.com:*",
    ],
    allowed_origins=[
        "https://x-replies-mcp.onrender.com",
        "https://x-replies-mcp.onrender.com:*",
    ],
)

app = mcp.streamable_http_app(
    stateless_http=True,
    json_response=True,
    transport_security=security,
)
