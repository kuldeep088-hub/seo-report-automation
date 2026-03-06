"""
Processor: Keywords
Computes rank changes, new rankings, and lost rankings from GSC data.
"""


def _build_keyword_map(keyword_list: list[dict]) -> dict[str, dict]:
    return {row["keyword"]: row for row in keyword_list}


def process_keywords(raw: dict) -> dict:
    """
    Input:  raw dict from collectors/search_console.py
    Output: keyword summary with movement analysis
    """
    curr_list = raw["current"]
    prev_list = raw["previous"]

    curr_map = _build_keyword_map(curr_list)
    prev_map = _build_keyword_map(prev_list)

    curr_keywords = set(curr_map.keys())
    prev_keywords = set(prev_map.keys())

    new_keywords = curr_keywords - prev_keywords
    lost_keywords = prev_keywords - curr_keywords
    common_keywords = curr_keywords & prev_keywords

    # Rank movers (only for keywords in both periods)
    improved, declined = [], []
    for kw in common_keywords:
        curr_pos = curr_map[kw]["position"]
        prev_pos = prev_map[kw]["position"]
        delta = round(prev_pos - curr_pos, 1)  # positive = improved (lower number = better)
        if delta > 0:
            improved.append({**curr_map[kw], "position_prev": prev_pos, "delta": delta})
        elif delta < 0:
            declined.append({**curr_map[kw], "position_prev": prev_pos, "delta": delta})

    improved.sort(key=lambda x: x["delta"], reverse=True)
    declined.sort(key=lambda x: x["delta"])

    # Top 10 keywords by clicks
    top_by_clicks = sorted(curr_list, key=lambda x: x["clicks"], reverse=True)[:10]

    # Totals
    total_clicks = sum(r["clicks"] for r in curr_list)
    total_impressions = sum(r["impressions"] for r in curr_list)
    total_clicks_prev = sum(r["clicks"] for r in prev_list)
    total_impressions_prev = sum(r["impressions"] for r in prev_list)

    in_top_10 = [kw for kw, data in curr_map.items() if data["position"] <= 10]
    in_top_3 = [kw for kw, data in curr_map.items() if data["position"] <= 3]

    def pct_change(curr_val, prev_val):
        if prev_val == 0:
            return 0.0
        return round(((curr_val - prev_val) / prev_val) * 100, 1)

    return {
        "month": raw["month"],
        "total_keywords_tracked": len(curr_list),
        "total_clicks": total_clicks,
        "total_clicks_prev": total_clicks_prev,
        "clicks_change_pct": pct_change(total_clicks, total_clicks_prev),
        "total_impressions": total_impressions,
        "total_impressions_prev": total_impressions_prev,
        "impressions_change_pct": pct_change(total_impressions, total_impressions_prev),
        "keywords_in_top_10": len(in_top_10),
        "keywords_in_top_3": len(in_top_3),
        "new_keywords_count": len(new_keywords),
        "lost_keywords_count": len(lost_keywords),
        "top_by_clicks": top_by_clicks,
        "most_improved": improved[:5],
        "most_declined": declined[:5],
        "new_keywords": [curr_map[kw] for kw in list(new_keywords)[:10]],
        "lost_keywords": [prev_map[kw] for kw in list(lost_keywords)[:10]],
    }
