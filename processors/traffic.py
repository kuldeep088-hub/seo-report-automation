"""
Processor: Traffic
Normalizes GA4 data and computes month-over-month changes.
"""


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 1)


def process_traffic(raw: dict) -> dict:
    """
    Input:  raw dict from collectors/google_analytics.py
    Output: structured summary with MoM changes
    """
    curr = raw["current"]["organic"]
    prev = raw["previous"]["organic"]
    curr_total = raw["current"]["total_sessions"]
    prev_total = raw["previous"]["total_sessions"]
    curr_channels = raw["current"]["all_channels"]

    organic_sessions = curr["sessions"]
    prev_organic = prev["sessions"]

    return {
        "month": raw["month"],
        "organic_sessions": organic_sessions,
        "organic_sessions_prev": prev_organic,
        "organic_sessions_change_pct": _pct_change(organic_sessions, prev_organic),
        "new_users": curr["new_users"],
        "new_users_prev": prev["new_users"],
        "new_users_change_pct": _pct_change(curr["new_users"], prev["new_users"]),
        "bounce_rate": curr["bounce_rate"],
        "avg_session_duration_sec": curr["avg_session_duration_sec"],
        "total_sessions": curr_total,
        "total_sessions_prev": prev_total,
        "total_sessions_change_pct": _pct_change(curr_total, prev_total),
        "top_channels": [
            {"channel": ch, "sessions": data["sessions"]}
            for ch, data in sorted(
                curr_channels.items(), key=lambda x: x[1]["sessions"], reverse=True
            )
        ],
    }
