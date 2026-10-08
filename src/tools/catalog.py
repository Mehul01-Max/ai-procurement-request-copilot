from __future__ import annotations

import re

from src.store import load_software_catalog

TOOL_SCHEMA = {
    "name": "search_software_catalog",
    "description": (
        "Find existing approved software that may already solve the need. "
        "Returns matches with software IDs, match scores, and an overlap flag."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Product need / use-case text"},
            "category": {"type": "string", "description": "Requested software category"},
            "vendor": {"type": "string", "description": "Requested vendor name"},
        },
        "required": ["query"],
    },
}

_STOP = frozenset("""a an the and or for to of in on with need needs want wants new existing app tool use using via from""".split())


def _tokens(text: object) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower())) - _STOP


def search_software_catalog(query: str, category: str | None = None, vendor: str | None = None) -> dict:
    """Score catalog rows by token overlap plus category/product/vendor boosts."""
    df = load_software_catalog()
    need = _tokens(query) | _tokens(category)
    matches: list[dict] = []
    for _, row in df.iterrows():
        hay = f"{row['product_name']} {row['category']} {row['vendor_name']} {row['notes']} {row['scope']}"
        score = len(need & _tokens(hay))
        same_category = bool(category) and str(row["category"]).strip().lower() == str(category).strip().lower()
        same_product = bool(_tokens(row["product_name"]) & _tokens(query))
        same_vendor = bool(vendor) and str(row["vendor_name"]).strip().lower() == str(vendor).strip().lower()
        if same_category:
            score += 3
        if same_vendor:
            score += 4
        if same_product:
            score += 5
        if score > 0:
            matches.append({
                "software_id": row["software_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "vendor_name": row["vendor_name"],
                "status": row["status"],
                "licensed_seats": int(row["licensed_seats"]),
                "scope": row["scope"],
                "match_score": score,
                "same_category": same_category,
                "same_product": same_product,
                "same_vendor": same_vendor,
            })
    matches.sort(key=lambda m: -m["match_score"])
    top = matches[:3]
    strong = any(m["same_product"] or m["same_vendor"] for m in top)
    return {
        "query": query,
        "matches": top,
        "overlap_found": any(m["same_product"] or m["same_vendor"] or m["same_category"] for m in top),
        "strong_overlap": strong,
        "references": [m["software_id"] for m in top],
    }
