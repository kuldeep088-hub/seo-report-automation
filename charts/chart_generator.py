"""
Chart Generator
Produces matplotlib charts for the SEO report.
Charts are saved to charts/<client_id>/<month>/ and their paths returned.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be before pyplot import
import matplotlib.pyplot as plt
import numpy as np

log = logging.getLogger(__name__)

CHART_DIR = Path("charts")

# Colour palette
BLUE   = "#1A73E8"
GREEN  = "#34A853"
ORANGE = "#FBBC04"
RED    = "#EA4335"
PURPLE = "#9334E6"
GREY   = "#5F6368"
PIE_COLORS = [BLUE, GREEN, ORANGE, RED, PURPLE, GREY, "#00ACC1", "#FF7043"]


def _out_dir(client_id: str, month: str) -> Path:
    d = CHART_DIR / client_id / month
    d.mkdir(parents=True, exist_ok=True)
    return d


def _month_label(month_str: str) -> str:
    return datetime.strptime(month_str, "%Y-%m").strftime("%b %Y")


def _prev_month(month_str: str) -> str:
    dt = datetime.strptime(month_str, "%Y-%m").replace(day=1)
    return (dt - timedelta(days=1)).strftime("%Y-%m")


def _load_gsc_cache(client_domain: str, month: str) -> list:
    client_id = client_domain.replace(".", "_")
    cache = Path("clients") / client_id / "data" / f"gsc_{month}.json"
    if not cache.exists():
        return []
    data = json.loads(cache.read_text(encoding="utf-8"))
    return [
        {
            "keyword":     row["keys"][0],
            "clicks":      row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr":         round(row.get("ctr", 0) * 100, 2),
            "position":    round(row.get("position", 0), 1),
        }
        for row in data.get("rows", [])
    ]


def _load_ga4_cache(client_domain: str, month: str) -> dict:
    client_id = client_domain.replace(".", "_")
    cache = Path("clients") / client_id / "data" / f"ga4_{month}.json"
    if not cache.exists():
        return {}
    data = json.loads(cache.read_text(encoding="utf-8"))
    channels = {}
    for row in data.get("rows", []):
        channel = row["dimensionValues"][0]["value"]
        mv = row["metricValues"]
        channels[channel] = {
            "sessions":               int(mv[0]["value"]),
            "new_users":              int(mv[1]["value"]),
            "bounce_rate":            round(float(mv[2]["value"]) * 100, 2),
            "avg_session_duration_sec": round(float(mv[3]["value"]), 1),
        }
    return channels


def _style_ax(ax, title: str):
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10, color="#202124")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=GREY, labelsize=8)
    ax.yaxis.label.set_color(GREY)
    ax.xaxis.label.set_color(GREY)


# ── Chart 1: Organic Clicks vs Impressions — 3 month trend ───────────────────

def chart_clicks_impressions_trend(context: dict, out_dir: Path) -> Path:
    domain = context["client"]["domain"]
    month  = context["report_month"]

    # Collect up to 3 months of GSC data from cache
    months_to_try = [_prev_month(_prev_month(month)), _prev_month(month), month]
    labels, clicks_data, impressions_data = [], [], []
    for mo in months_to_try:
        rows = _load_gsc_cache(domain, mo)
        if rows:
            labels.append(_month_label(mo))
            clicks_data.append(sum(r["clicks"] for r in rows))
            impressions_data.append(sum(r["impressions"] for r in rows))

    # Fallback to processed keyword data if cache is thin
    if len(labels) < 2:
        k = context["keywords"]
        labels = [_month_label(_prev_month(month)), _month_label(month)]
        clicks_data = [k["total_clicks_prev"], k["total_clicks"]]
        impressions_data = [k["total_impressions_prev"], k["total_impressions"]]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="white")
    bars1 = ax.bar(x - width / 2, clicks_data, width, label="Clicks", color=BLUE, alpha=0.9)
    bars2 = ax.bar(x + width / 2, impressions_data, width, label="Impressions", color=GREEN, alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Count")
    ax.legend(loc="upper left", fontsize=9)
    _style_ax(ax, "Organic Clicks vs Impressions — 3 Month Trend")

    max_click = max(clicks_data) if clicks_data else 1
    max_imp   = max(impressions_data) if impressions_data else 1
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_click * 0.01,
                f"{int(bar.get_height()):,}", ha="center", va="bottom", fontsize=7, color=GREY)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_imp * 0.01,
                f"{int(bar.get_height()):,}", ha="center", va="bottom", fontsize=7, color=GREY)

    fig.tight_layout()
    path = out_dir / "clicks_impressions_trend.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 2: Traffic channels pie chart ──────────────────────────────────────

def chart_traffic_channels(context: dict, out_dir: Path) -> Path:
    channels = context["traffic"]["top_channels"]
    total = sum(c["sessions"] for c in channels) or 1

    main, other = [], 0
    for c in channels:
        if c["sessions"] / total >= 0.03:
            main.append(c)
        else:
            other += c["sessions"]
    if other:
        main.append({"channel": "Other", "sessions": other})

    labels = [c["channel"] for c in main]
    sizes  = [c["sessions"] for c in main]
    colors = PIE_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="white")
    wedges, _, autotexts = ax.pie(
        sizes, labels=None, colors=colors,
        autopct=lambda p: f"{p:.1f}%" if p >= 4 else "",
        startangle=140, pctdistance=0.78,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color("white")
        at.set_fontweight("bold")

    legend_labels = [f"{l}  ({s:,} sessions)" for l, s in zip(labels, sizes)]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)
    ax.set_title("Traffic by Channel — GA4", fontsize=12, fontweight="bold", pad=12, color="#202124")

    fig.tight_layout()
    path = out_dir / "traffic_channels.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 3: Keyword ranking trend ───────────────────────────────────────────

def chart_keyword_ranking_trend(context: dict, out_dir: Path) -> Path:
    domain = context["client"]["domain"]
    month  = context["report_month"]
    prev   = _prev_month(month)

    curr_rows = _load_gsc_cache(domain, month)
    prev_rows = _load_gsc_cache(domain, prev)
    curr_map  = {r["keyword"]: r["position"] for r in curr_rows}
    prev_map  = {r["keyword"]: r["position"] for r in prev_rows}

    # Top keywords by clicks that exist in both months
    top_kws = [kw["keyword"] for kw in context["keywords"]["top_by_clicks"][:10]]
    plot_kws = [kw for kw in top_kws if kw in curr_map and kw in prev_map][:7]

    if not plot_kws:
        plot_kws = list(curr_map.keys())[:7]

    curr_positions = [round(curr_map[kw], 1) for kw in plot_kws]
    prev_positions = [round(prev_map.get(kw, curr_map[kw]), 1) for kw in plot_kws]
    short_labels   = [kw[:32] + "…" if len(kw) > 32 else kw for kw in plot_kws]

    x     = np.arange(len(short_labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="white")
    ax.bar(x - width / 2, prev_positions, width, label=_month_label(prev), color=GREY,  alpha=0.75)
    bars2 = ax.bar(x + width / 2, curr_positions, width, label=_month_label(month), color=BLUE, alpha=0.9)

    ax.invert_yaxis()
    ax.set_ylabel("Avg Position (lower = better)")
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, rotation=28, ha="right", fontsize=7)
    ax.legend(fontsize=9)
    _style_ax(ax, "Keyword Ranking Positions — Top Keywords")

    for bar in bars2:
        val = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.2,
                f"{val:.1f}", ha="center", va="top", fontsize=7, color=BLUE)

    fig.tight_layout()
    path = out_dir / "keyword_ranking_trend.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 4: Top queries by organic clicks (landing pages proxy) ──────────────

def chart_top_landing_pages(context: dict, out_dir: Path) -> Path:
    top = context["keywords"]["top_by_clicks"][:8]
    labels = [kw["keyword"][:38] + "…" if len(kw["keyword"]) > 38 else kw["keyword"] for kw in top]
    clicks = [kw["clicks"] for kw in top]
    colors = [BLUE if i % 2 == 0 else "#4285F4" for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="white")
    bars = ax.barh(labels[::-1], clicks[::-1], color=colors[::-1], alpha=0.9, height=0.6)

    max_c = max(clicks) if clicks else 1
    for bar in bars:
        w = bar.get_width()
        ax.text(w + max_c * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{int(w):,}", va="center", fontsize=8, color=GREY)

    ax.set_xlabel("Organic Clicks")
    ax.set_xlim(0, max_c * 1.18)
    _style_ax(ax, "Top Queries by Organic Clicks (Source: GSC)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout()
    path = out_dir / "top_landing_pages.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 5: Engagement metrics ───────────────────────────────────────────────

def chart_engagement_metrics(context: dict, out_dir: Path) -> Path:
    domain = context["client"]["domain"]
    month  = context["report_month"]
    prev   = _prev_month(month)
    t      = context["traffic"]

    curr_channels = _load_ga4_cache(domain, month)
    prev_channels = _load_ga4_cache(domain, prev)

    def weighted(channels, metric):
        total = sum(c["sessions"] for c in channels.values()) or 1
        return sum(c[metric] * c["sessions"] for c in channels.values()) / total

    curr_bounce   = weighted(curr_channels, "bounce_rate")   if curr_channels else t["bounce_rate"]
    prev_bounce   = weighted(prev_channels, "bounce_rate")   if prev_channels else t["bounce_rate"]
    curr_duration = weighted(curr_channels, "avg_session_duration_sec") if curr_channels else t["avg_session_duration_sec"]
    prev_duration = weighted(prev_channels, "avg_session_duration_sec") if prev_channels else t["avg_session_duration_sec"]

    month_labels = [_month_label(prev), _month_label(month)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.5), facecolor="white")

    # Bounce rate
    bounce_vals  = [round(prev_bounce, 1), round(curr_bounce, 1)]
    bounce_colors = [GREY, RED if curr_bounce > prev_bounce else GREEN]
    b1 = ax1.bar(month_labels, bounce_vals, color=bounce_colors, alpha=0.85, width=0.45)
    ax1.set_ylabel("Bounce Rate (%)")
    ax1.set_ylim(0, max(bounce_vals) * 1.35 if bounce_vals else 100)
    _style_ax(ax1, "Bounce Rate")
    for bar in b1:
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{bar.get_height():.1f}%", ha="center", fontsize=10, fontweight="bold", color="#202124")

    # Avg session duration
    dur_vals   = [round(prev_duration, 0), round(curr_duration, 0)]
    dur_colors = [GREY, GREEN if curr_duration >= prev_duration else RED]
    b2 = ax2.bar(month_labels, dur_vals, color=dur_colors, alpha=0.85, width=0.45)
    ax2.set_ylabel("Seconds")
    ax2.set_ylim(0, max(dur_vals) * 1.35 if dur_vals else 300)
    _style_ax(ax2, "Avg Session Duration")
    for bar in b2:
        s = int(bar.get_height())
        label = f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(dur_vals) * 0.02,
                 label, ha="center", fontsize=10, fontweight="bold", color="#202124")

    fig.suptitle("Engagement Metrics — Month over Month", fontsize=12, fontweight="bold",
                 color="#202124", y=1.02)
    fig.tight_layout()
    path = out_dir / "engagement_metrics.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 6: Goal Performance — target vs actual ─────────────────────────────

def chart_goal_performance(context: dict, out_dir: Path) -> Path:
    targets = context.get("targets", {})
    t, k, b = context["traffic"], context["keywords"], context["backlinks"]

    metrics = [
        ("Organic\nSessions", targets.get("organic_sessions_goal", 0), t["organic_sessions"]),
        ("Top 10\nKeywords",  targets.get("top_10_keywords_goal", 0),  k["keywords_in_top_10"]),
        ("New\nBacklinks",    targets.get("new_backlinks_goal", 0),     b["new_backlinks_count"]),
    ]

    labels      = [m[0] for m in metrics]
    target_vals = [m[1] for m in metrics]
    actual_vals = [m[2] for m in metrics]
    bar_colors  = [GREEN if a >= tgt else RED for a, tgt in zip(actual_vals, target_vals)]

    x     = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="white")
    ax.bar(x - width / 2, target_vals, width, label="Target", color=GREY, alpha=0.55)
    bars = ax.bar(x + width / 2, actual_vals, width, label="Actual", color=bar_colors, alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.legend(fontsize=9)
    _style_ax(ax, "Goal Performance — Target vs Actual")

    max_val = max(max(target_vals), max(actual_vals)) if target_vals else 1
    for bar, color in zip(bars, bar_colors):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max_val * 0.02,
                f"{int(bar.get_height()):,}",
                ha="center", fontsize=9, fontweight="bold", color=color)

    fig.tight_layout()
    path = out_dir / "goal_performance.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 7: Backlink Overview — new vs lost + dofollow breakdown ─────────────

def chart_backlink_overview(context: dict, out_dir: Path) -> Path:
    b = context["backlinks"]
    new_bl  = b["new_backlinks_count"]
    lost_bl = b["lost_backlinks_count"]
    do_new  = b.get("dofollow_new", 0)
    do_lost = b.get("dofollow_lost", 0)
    nf_new  = max(0, new_bl - do_new)
    nf_lost = max(0, lost_bl - do_lost)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.5), facecolor="white")

    # New vs lost
    cats   = ["New Backlinks", "Lost Backlinks"]
    vals   = [new_bl, lost_bl]
    colors = [GREEN, RED]
    b1 = ax1.bar(cats, vals, color=colors, alpha=0.85, width=0.45)
    _style_ax(ax1, "New vs Lost Backlinks")
    max_v = max(vals) if vals else 1
    for bar in b1:
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max_v * 0.03,
                 str(int(bar.get_height())),
                 ha="center", fontsize=11, fontweight="bold", color="#202124")

    # Dofollow breakdown
    x2    = np.arange(2)
    w2    = 0.35
    ax2.bar(x2 - w2 / 2, [do_new, do_lost],  w2, label="Dofollow",  color=[GREEN, RED],  alpha=0.85)
    ax2.bar(x2 + w2 / 2, [nf_new, nf_lost],  w2, label="Nofollow",  color=[GREY, GREY],  alpha=0.5)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(["New Links", "Lost Links"])
    ax2.legend(fontsize=8)
    _style_ax(ax2, "Dofollow vs Nofollow Breakdown")

    fig.tight_layout()
    path = out_dir / "backlink_overview.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 8: CTR by Top Keywords ──────────────────────────────────────────────

def chart_ctr_top_keywords(context: dict, out_dir: Path) -> Path:
    top    = context["keywords"]["top_by_clicks"][:8]
    labels = [kw["keyword"][:32] + "…" if len(kw["keyword"]) > 32 else kw["keyword"]
              for kw in top]
    ctrs   = [kw["ctr"] for kw in top]
    colors = [GREEN if c >= 3 else BLUE if c >= 1 else ORANGE for c in ctrs]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="white")
    bars = ax.barh(labels[::-1], ctrs[::-1], color=colors[::-1], alpha=0.9, height=0.6)

    max_c = max(ctrs) if ctrs else 1
    for bar in bars:
        w = bar.get_width()
        ax.text(w + max_c * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{w:.1f}%", va="center", fontsize=8, color=GREY)

    ax.set_xlabel("Click-Through Rate (%)")
    ax.set_xlim(0, max_c * 1.2)
    _style_ax(ax, "Click-Through Rate by Top Keywords (Source: GSC)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout()
    path = out_dir / "ctr_top_keywords.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Public entry point ────────────────────────────────────────────────────────

def generate_all_charts(context: dict, client_id: str) -> dict:
    """Generate all 8 SEO charts. Returns dict mapping chart name → Path."""
    month   = context["report_month"]
    out_dir = _out_dir(client_id, month)
    log.info("Generating charts for %s / %s ...", client_id, month)

    charts = {
        "clicks_impressions": chart_clicks_impressions_trend(context, out_dir),
        "traffic_channels":   chart_traffic_channels(context, out_dir),
        "keyword_rankings":   chart_keyword_ranking_trend(context, out_dir),
        "top_pages":          chart_top_landing_pages(context, out_dir),
        "engagement":         chart_engagement_metrics(context, out_dir),
        "goal_performance":   chart_goal_performance(context, out_dir),
        "backlink_overview":  chart_backlink_overview(context, out_dir),
        "ctr_keywords":       chart_ctr_top_keywords(context, out_dir),
    }

    log.info("All %d charts generated.", len(charts))
    return charts
