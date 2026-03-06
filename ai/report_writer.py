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
        dr = bl.get("domain_rating_source", "?")
        url = bl.get("url_from", "?")
        anchor = bl.get("anchor", "?")
        lines.append(f"  - DR{dr} | {url} | anchor: '{anchor}'")
    return "\n".join(lines) if lines else "  None"


def _extract_next_month_plan(work_log: str) -> str:
    """Pull the '## Next Month Plan' section from work_log.md."""
    if "## Next Month Plan" not in work_log:
        return work_log.strip()
    parts = work_log.split("## Next Month Plan", 1)
    plan_text = parts[1].strip()
    # Stop at the next ## section if present
    if "\n##" in plan_text:
        plan_text = plan_text.split("\n##")[0].strip()
    return plan_text


def _extract_work_done(work_log: str) -> str:
    """Pull the '## Work Done This Month' section from work_log.md."""
    if "## Work Done This Month" not in work_log:
        return ""
    parts = work_log.split("## Work Done This Month", 1)
    section = parts[1].strip()
    if "\n##" in section:
        section = section.split("\n##")[0].strip()
    return section


# ── Section generators ───────────────────────────────────────────────────────

def generate_executive_summary(ctx: dict) -> str:
    log.info("Generating executive summary...")
    t, k, b = ctx["traffic"], ctx["keywords"], ctx["backlinks"]
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
    )
    return _call_claude(prompt)


def generate_traffic_section(ctx: dict) -> str:
    log.info("Generating traffic section...")
    t = ctx["traffic"]
    prompt = _load_prompt("traffic_section").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        organic_sessions=t["organic_sessions"],
        organic_sessions_prev=t["organic_sessions_prev"],
        organic_sessions_change_pct=t["organic_sessions_change_pct"],
        new_users=t["new_users"],
        new_users_prev=t["new_users_prev"],
        new_users_change_pct=t["new_users_change_pct"],
        bounce_rate=t["bounce_rate"],
        avg_session_duration_sec=t["avg_session_duration_sec"],
        total_sessions=t["total_sessions"],
        total_sessions_prev=t["total_sessions_prev"],
        total_sessions_change_pct=t["total_sessions_change_pct"],
        top_channels_text=_fmt_channels(t["top_channels"]),
    )
    return _call_claude(prompt)


def generate_keywords_section(ctx: dict) -> str:
    log.info("Generating keywords section...")
    k = ctx["keywords"]
    prompt = _load_prompt("keywords_section").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        total_keywords_tracked=k["total_keywords_tracked"],
        keywords_in_top_10=k["keywords_in_top_10"],
        keywords_in_top_3=k["keywords_in_top_3"],
        new_keywords_count=k["new_keywords_count"],
        lost_keywords_count=k["lost_keywords_count"],
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
    prompt = _load_prompt("next_steps").format(
        client_name=ctx["client"]["name"],
        domain=ctx["client"]["domain"],
        report_month=ctx["report_month"],
        next_month_plan=next_month_plan,
        organic_sessions=t["organic_sessions"],
        organic_sessions_change_pct=t["organic_sessions_change_pct"],
        keywords_in_top_10=k["keywords_in_top_10"],
        domain_rating=b["domain_rating"],
    )
    return _call_claude(prompt)


# ── Demo mode (no API credits needed) ────────────────────────────────────────

def generate_demo_report(ctx: dict) -> dict:
    """
    Returns placeholder text for every section so the full pipeline
    (processing → PDF export) can be tested without API credits.
    """
    t, k, b = ctx["traffic"], ctx["keywords"], ctx["backlinks"]
    client_name = ctx["client"]["name"]
    month = ctx["report_month"]
    work_done = _extract_work_done(ctx["work_log"])

    return {
        "executive_summary": (
            f"This is a demo report for {client_name} covering {month}. "
            f"Organic sessions reached {t['organic_sessions']:,}, "
            f"a change of {t['organic_sessions_change_pct']:+.1f}% versus the previous month. "
            f"The site recorded {k['total_clicks']:,} organic clicks and {k['total_impressions']:,} impressions in Google Search. "
            f"Overall the site continues to build its online presence in a competitive landscape.\n\n"
            f"[This section will be written by Claude AI once API credits are added.]"
        ),
        "traffic_analysis": (
            f"In {month}, the website received {t['organic_sessions']:,} organic sessions "
            f"({t['organic_sessions_change_pct']:+.1f}% vs previous month). "
            f"New users totalled {t['new_users']:,} and the average session duration was "
            f"{t['avg_session_duration_sec']} seconds.\n\n"
            f"[This section will be written by Claude AI once API credits are added.]"
        ),
        "keyword_rankings": (
            f"The site currently ranks for {k['total_keywords_tracked']} keywords, "
            f"with {k['keywords_in_top_10']} in the top 10 and {k['keywords_in_top_3']} in the top 3. "
            f"This month {k['new_keywords_count']} new keywords entered rankings "
            f"and {k['lost_keywords_count']} were lost.\n\n"
            f"[This section will be written by Claude AI once API credits are added.]"
        ),
        "backlinks": (
            f"This month the site gained {b['new_backlinks_count']} new backlinks "
            f"and lost {b['lost_backlinks_count']}. "
            f"The current Domain Rating is {b['domain_rating']} "
            f"with {b['referring_domains']} referring domains.\n\n"
            f"[This section will be written by Claude AI once API credits are added.]"
        ),
        "work_done": work_done,
        "next_steps": (
            "[This section will be written by Claude AI once API credits are added.]\n"
            "- Continue building high-quality backlinks\n"
            "- Publish new content targeting priority keywords\n"
            "- Monitor and improve Core Web Vitals\n"
            "- Review and optimise underperforming pages"
        ),
    }


# ── Main entry ───────────────────────────────────────────────────────────────

def generate_report(ctx: dict, demo: bool = False) -> dict:
    """
    Generate all report sections.
    Pass demo=True to skip Claude API and use placeholder text instead.
    """
    if demo:
        log.info("Demo mode: skipping Claude API, using placeholder text.")
        return generate_demo_report(ctx)

    work_done = _extract_work_done(ctx["work_log"])

    sections = {
        "executive_summary": generate_executive_summary(ctx),
        "traffic_analysis": generate_traffic_section(ctx),
        "keyword_rankings": generate_keywords_section(ctx),
        "backlinks": generate_backlinks_section(ctx),
        "work_done": work_done,
        "next_steps": generate_next_steps(ctx),
    }

    log.info("All report sections generated successfully.")
    return sections
