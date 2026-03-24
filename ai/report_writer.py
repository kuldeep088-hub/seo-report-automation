"""
AI Report Writer
Uses Claude API to generate each section of the SEO report.
"""

import logging
import os
from pathlib import Path

import anthropic

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


# ── Prompt formatters ────────────────────────────────────────────────────────

def _fmt_channels(channels: list[dict]) -> str:
    return "\n".join(
        f"  - {c['channel']}: {c['sessions']:,} sessions"
        for c in channels[:6]
    )


def _fmt_keyword_list(keywords: list[dict], mode: str = "improved") -> str:
    lines = []
    for kw in keywords:
        if mode == "improved":
            lines.append(
                f"  - '{kw['keyword']}': pos {kw['position_prev']} → {kw['position']} (+{kw['delta']})"
            )
        elif mode == "declined":
            lines.append(
                f"  - '{kw['keyword']}': pos {kw['position_prev']} → {kw['position']} ({kw['delta']})"
            )
        elif mode == "clicks":
            lines.append(
                f"  - '{kw['keyword']}': {kw['clicks']} clicks, pos {kw['position']}"
            )
    return "\n".join(lines) if lines else "  None"


def _fmt_backlinks(backlinks: list[dict]) -> str:
    lines = []
    for bl in backlinks[:5]:
        dr     = bl.get("domain_rating_source", "?")
        url    = bl.get("url_from", "?")
        anchor = bl.get("anchor", "?")
        lines.append(f"  - DR{dr} | {url} | anchor: '{anchor}'")
    return "\n".join(lines) if lines else "  None"


def _extract_next_month_plan(work_log: str) -> str:
    if "## Next Month Plan" not in work_log:
        return work_log.strip()
    parts = work_log.split("## Next Month Plan", 1)
    plan_text = parts[1].strip()
    if "\n##" in plan_text:
        plan_text = plan_text.split("\n##")[0].strip()
    return plan_text


def _extract_work_done(work_log: str) -> str:
    if "## Work Done This Month" not in work_log:
        return ""
    parts = work_log.split("## Work Done This Month", 1)
    section = parts[1].strip()
    if "\n##" in section:
        section = section.split("\n##")[0].strip()
    return section


def _get_mobile_score(ctx: dict):
    ps = ctx.get("pagespeed", {})
    return ps.get("mobile", {}).get("performance_score") or "N/A"


def _get_top_landing_page(ctx: dict) -> tuple[str, int]:
    pages = ctx.get("landing_pages", {}).get("current", [])
    if pages:
        top = pages[0]
        return top["page"], top["clicks"]
    return "N/A", 0


def _get_goal_status(ctx: dict) -> str:
    actual = ctx["traffic"]["organic_sessions"]
    target = ctx.get("targets", {}).get("organic_sessions_goal", 0)
    if not target:
        return "N/A"
    return "On Track" if actual >= target else "Behind Target"


def _fmt_channel_changes(channels_curr: list[dict]) -> tuple[str, str]:
    if len(channels_curr) < 2:
        return "Organic Search", "N/A"
    sorted_ch = sorted(channels_curr, key=lambda x: x["sessions"], reverse=True)
    biggest_growth   = f"{sorted_ch[0]['channel']} ({sorted_ch[0]['sessions']:,} sessions)"
    biggest_decline  = f"{sorted_ch[-1]['channel']} ({sorted_ch[-1]['sessions']:,} sessions)"
    return biggest_growth, biggest_decline


def _find_high_imp_low_ctr(keywords: list[dict]) -> tuple[str, int, float]:
    """Find keyword with high impressions but low CTR — best click opportunity."""
    candidates = [k for k in keywords if k.get("impressions", 0) > 200]
    if not candidates:
        candidates = keywords
    if not candidates:
        return "N/A", 0, 0.0
    best = min(candidates, key=lambda k: k.get("ctr", 100))
    return best["keyword"], best["impressions"], best["ctr"]


def _get_near_top_count(keywords: list[dict]) -> int:
    return sum(1 for k in keywords if 4.0 <= k.get("position", 99) <= 10.9)


def _get_low_performance_pages(ctx: dict) -> str:
    pages = ctx.get("landing_pages", {}).get("current", [])
    low = [p for p in pages if p.get("ctr", 100) < 2.0 or p.get("position", 0) > 10][:3]
    if not low:
        return "None identified"
    return ", ".join(p["page"].replace("https://", "").rstrip("/") for p in low)


def _organic_share_pct(traffic: dict) -> float:
    total = traffic.get("total_sessions", 1) or 1
    return round(traffic["organic_sessions"] / total * 100, 1)


# ── Section generators ───────────────────────────────────────────────────────

def generate_executive_summary(ctx: dict) -> str:
    log.info("Generating executive summary...")
    t, k, b = ctx["traffic"], ctx["keywords"], ctx["backlinks"]
    top_page, top_page_clicks = _get_top_landing_page(ctx)
    prompt = _load_prompt("executive_summary").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        organic_sessions=t["organic_sessions"],
        organic_sessions_change_pct=t["organic_sessions_change_pct"],
        total_clicks=k["total_clicks"],
        clicks_change_pct=k["clicks_change_pct"],
        total_impressions=k["total_impressions"],
        impressions_change_pct=k["impressions_change_pct"],
        keywords_in_top_10=k["keywords_in_top_10"],
        new_backlinks_count=b["new_backlinks_count"],
        domain_rating=b["domain_rating"],
        mobile_perf_score=_get_mobile_score(ctx),
        top_landing_page=top_page,
        top_page_clicks=top_page_clicks,
        organic_sessions_goal=ctx.get("targets", {}).get("organic_sessions_goal", "N/A"),
        goal_status=_get_goal_status(ctx),
    )
    return _call_claude(prompt)


def generate_traffic_section(ctx: dict) -> str:
    log.info("Generating traffic section...")
    t = ctx["traffic"]
    biggest_growth, biggest_decline = _fmt_channel_changes(t["top_channels"])
    prompt = _load_prompt("traffic_section").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        organic_sessions=t["organic_sessions"],
        organic_sessions_prev=t["organic_sessions_prev"],
        organic_sessions_change_pct=t["organic_sessions_change_pct"],
        organic_share_pct=_organic_share_pct(t),
        new_users=t["new_users"],
        new_users_prev=t["new_users_prev"],
        new_users_change_pct=t["new_users_change_pct"],
        bounce_rate=t["bounce_rate"],
        avg_session_duration_sec=t["avg_session_duration_sec"],
        total_sessions=t["total_sessions"],
        total_sessions_prev=t["total_sessions_prev"],
        total_sessions_change_pct=t["total_sessions_change_pct"],
        top_channels_text=_fmt_channels(t["top_channels"]),
        biggest_channel_growth=biggest_growth,
        biggest_channel_decline=biggest_decline,
    )
    return _call_claude(prompt)


def generate_keywords_section(ctx: dict) -> str:
    log.info("Generating keywords section...")
    k = ctx["keywords"]
    all_keywords = ctx.get("_raw_keywords_current", k.get("top_by_clicks", []))
    hi_kw, hi_imp, hi_ctr = _find_high_imp_low_ctr(k.get("top_by_clicks", []))
    avg_ctr = (
        sum(kw.get("ctr", 0) for kw in k.get("top_by_clicks", [])[:10]) /
        max(len(k.get("top_by_clicks", [])[:10]), 1)
    )
    prompt = _load_prompt("keywords_section").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        total_keywords_tracked=k["total_keywords_tracked"],
        keywords_in_top_10=k["keywords_in_top_10"],
        keywords_in_top_3=k["keywords_in_top_3"],
        new_keywords_count=k["new_keywords_count"],
        lost_keywords_count=k["lost_keywords_count"],
        avg_ctr_top10=avg_ctr,
        high_imp_low_ctr_keyword=hi_kw,
        high_imp_low_ctr_impressions=hi_imp,
        high_imp_low_ctr_ctr=hi_ctr,
        most_improved_text=_fmt_keyword_list(k["most_improved"], "improved"),
        most_declined_text=_fmt_keyword_list(k["most_declined"], "declined"),
        top_by_clicks_text=_fmt_keyword_list(k["top_by_clicks"], "clicks"),
    )
    return _call_claude(prompt)


def generate_backlinks_section(ctx: dict) -> str:
    log.info("Generating backlinks section...")
    b = ctx["backlinks"]
    prompt = _load_prompt("backlinks_section").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        new_backlinks_count=b["new_backlinks_count"],
        lost_backlinks_count=b["lost_backlinks_count"],
        dofollow_new=b["dofollow_new"],
        dofollow_lost=b["dofollow_lost"],
        avg_dr_new_backlinks=b["avg_dr_new_backlinks"],
        domain_rating=b["domain_rating"],
        total_backlinks=b["total_backlinks"],
        referring_domains=b["referring_domains"],
        top_new_backlinks_text=_fmt_backlinks(b["top_new_backlinks"]),
    )
    return _call_claude(prompt)


def generate_next_steps(ctx: dict) -> str:
    log.info("Generating next steps section...")
    t, k, b = ctx["traffic"], ctx["keywords"], ctx["backlinks"]
    next_month_plan = _extract_next_month_plan(ctx["work_log"])
    near_top = _get_near_top_count(k.get("top_by_clicks", []))
    prompt = _load_prompt("next_steps").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        next_month_plan=next_month_plan,
        organic_sessions=t["organic_sessions"],
        organic_sessions_change_pct=t["organic_sessions_change_pct"],
        keywords_in_top_10=k["keywords_in_top_10"],
        domain_rating=b["domain_rating"],
        mobile_perf_score=_get_mobile_score(ctx),
        near_top_keywords_count=near_top,
        low_performance_pages=_get_low_performance_pages(ctx),
    )
    return _call_claude(prompt)


# ── Demo mode (no API credits needed) ────────────────────────────────────────

def generate_demo_report(ctx: dict) -> dict:
    t, k, b = ctx["traffic"], ctx["keywords"], ctx["backlinks"]
    client_name = ctx["client"]["name"]
    month = ctx["report_month"]
    work_done = _extract_work_done(ctx["work_log"])
    mobile_score = _get_mobile_score(ctx)
    top_page, top_clicks = _get_top_landing_page(ctx)

    return {
        "executive_summary": (
            f"This is a demo report for {client_name} covering {month}. "
            f"Organic sessions reached {t['organic_sessions']:,} ({t['organic_sessions_change_pct']:+.1f}% vs last month). "
            f"The site recorded {k['total_clicks']:,} organic clicks and {k['total_impressions']:,} impressions. "
            f"Top landing page: {top_page} with {top_clicks} clicks. "
            f"Mobile performance score: {mobile_score}/100.\n\n"
            f"[Written by Claude AI in live mode]"
        ),
        "traffic_analysis": (
            f"In {month}, organic sessions were {t['organic_sessions']:,} ({t['organic_sessions_change_pct']:+.1f}% vs last month), "
            f"representing {_organic_share_pct(t):.1f}% of total traffic. "
            f"New users: {t['new_users']:,}. Bounce rate: {t['bounce_rate']}%.\n\n"
            f"[Written by Claude AI in live mode]"
        ),
        "keyword_rankings": (
            f"Tracking {k['total_keywords_tracked']} keywords: {k['keywords_in_top_10']} in top 10, {k['keywords_in_top_3']} in top 3. "
            f"{k['new_keywords_count']} new keywords entered rankings, {k['lost_keywords_count']} lost.\n\n"
            f"[Written by Claude AI in live mode]"
        ),
        "backlinks": (
            f"Gained {b['new_backlinks_count']} new backlinks, lost {b['lost_backlinks_count']}. "
            f"Domain Rating: {b['domain_rating']} | Referring Domains: {b['referring_domains']}.\n\n"
            f"[Written by Claude AI in live mode]"
        ),
        "work_done": work_done,
        "next_steps": (
            f"[Written by Claude AI in live mode]\n"
            f"- Continue building high-quality backlinks toward {ctx.get('targets', {}).get('new_backlinks_goal', 10)} goal\n"
            f"- Improve mobile performance score (currently {mobile_score}/100)\n"
            f"- Publish new content targeting priority keywords\n"
            f"- Review and optimise underperforming pages"
        ),
    }


# ── Main entry ───────────────────────────────────────────────────────────────

def generate_report(ctx: dict, demo: bool = False) -> dict:
    if demo:
        log.info("Demo mode: skipping Claude API, using placeholder text.")
        return generate_demo_report(ctx)

    work_done = _extract_work_done(ctx["work_log"])

    sections = {
        "executive_summary": generate_executive_summary(ctx),
        "traffic_analysis":  generate_traffic_section(ctx),
        "keyword_rankings":  generate_keywords_section(ctx),
        "backlinks":         generate_backlinks_section(ctx),
        "work_done":         work_done,
        "next_steps":        generate_next_steps(ctx),
    }

    log.info("All report sections generated successfully.")
    return sections
