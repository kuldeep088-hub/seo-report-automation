"""
Chart Generator
Produces 10 professional matplotlib charts from real GA4 and GSC data.
Charts are saved to charts/<client_id>/<month>/ and their paths returned.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — must be before pyplot import
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

log = logging.getLogger(__name__)

CHART_DIR = Path("charts")

# ── Colour palette ────────────────────────────────────────────────────────────
BLUE   = "#1A73E8"
GREEN  = "#34A853"
ORANGE = "#FBBC04"
RED    = "#EA4335"
PURPLE = "#9334E6"
GREY   = "#5F6368"
LIGHT_BLUE   = "#D2E3FC"
LIGHT_GREEN  = "#CEEAD6"
PIE_COLORS   = [BLUE, GREEN, ORANGE, RED, PURPLE, GREY, "#00ACC1", "#FF7043"]

# ── Global style (applied once at import) ─────────────────────────────────────
plt.rcParams.update({
    "font.family":         "DejaVu Sans",
    "font.size":           10,
    "axes.spines.top":     False,
    "axes.spines.right":   False,
    "axes.grid":           True,
    "grid.color":          "#F1F3F4",
    "grid.linewidth":      0.8,
    "axes.edgecolor":      "#DADCE0",
    "figure.facecolor":    "white",
    "axes.facecolor":      "white",
    "xtick.color":         "#5F6368",
    "ytick.color":         "#5F6368",
    "axes.labelcolor":     "#5F6368",
    "legend.framealpha":   0.95,
    "legend.edgecolor":    "#DADCE0",
    "legend.fontsize":     9,
})


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    """Load raw GSC rows from cache. Returns [] if not available."""
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
    """Load GA4 channel data from cache. Returns {} if not available."""
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
            "sessions":                 int(mv[0]["value"]),
            "new_users":                int(mv[1]["value"]),
            "bounce_rate":              round(float(mv[2]["value"]) * 100, 2),
            "avg_session_duration_sec": round(float(mv[3]["value"]), 1),
        }
    return channels


def _organic_sessions_from_cache(client_domain: str, month: str) -> int:
    """Return organic search sessions for a given month from GA4 cache."""
    channels = _load_ga4_cache(client_domain, month)
    for ch, data in channels.items():
        if "organic" in ch.lower():
            return data["sessions"]
    return 0


def _title(ax, text: str):
    ax.set_title(text, fontsize=12, fontweight="bold", pad=12, color="#202124")


def _annotate_bar(ax, bar, fmt="{:,}", offset_pct=0.02, fontsize=9, color="#202124"):
    """Place a value label above a vertical bar."""
    val = bar.get_height()
    max_y = ax.get_ylim()[1] or 1
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        val + max_y * offset_pct,
        fmt.format(int(val)),
        ha="center", va="bottom", fontsize=fontsize,
        fontweight="bold", color=color,
    )


def _annotate_hbar(ax, bar, fmt="{:,}", offset_pct=0.01, fontsize=8, color=GREY):
    """Place a value label to the right of a horizontal bar."""
    w = bar.get_width()
    max_x = ax.get_xlim()[1] or 1
    ax.text(
        w + max_x * offset_pct,
        bar.get_y() + bar.get_height() / 2,
        fmt.format(int(w)),
        va="center", fontsize=fontsize, color=color,
    )


# ── Chart 1: GSC Clicks vs Impressions — dual-axis line ──────────────────────

def chart_gsc_clicks_impressions(context: dict, out_dir: Path) -> Path:
    """
    Dual-axis line chart: organic clicks (left) vs impressions (right)
    over up to 3 months of Google Search Console data.
    File: gsc_clicks_impressions.png
    """
    domain = context["client"]["domain"]
    month  = context["report_month"]

    months_to_try = [_prev_month(_prev_month(month)), _prev_month(month), month]
    labels, clicks_data, imp_data = [], [], []
    for mo in months_to_try:
        rows = _load_gsc_cache(domain, mo)
        if rows:
            labels.append(_month_label(mo))
            clicks_data.append(sum(r["clicks"] for r in rows))
            imp_data.append(sum(r["impressions"] for r in rows))

    # Fallback to processed context data if cache is thin
    if len(labels) < 2:
        k = context["keywords"]
        labels      = [_month_label(_prev_month(month)), _month_label(month)]
        clicks_data = [k["total_clicks_prev"], k["total_clicks"]]
        imp_data    = [k["total_impressions_prev"], k["total_impressions"]]

    fig, ax1 = plt.subplots(figsize=(9, 4.5))

    # Clicks — left axis (blue)
    ax1.plot(labels, clicks_data, color=BLUE, linewidth=2.5, marker="o",
             markersize=9, label="Organic Clicks", zorder=5)
    ax1.fill_between(labels, clicks_data, alpha=0.10, color=BLUE)
    ax1.set_ylabel("Organic Clicks", color=BLUE, fontsize=10)
    ax1.tick_params(axis="y", labelcolor=BLUE, labelsize=9)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    for i, (lbl, val) in enumerate(zip(labels, clicks_data)):
        ax1.annotate(f"{val:,}", (lbl, val),
                     textcoords="offset points", xytext=(0, 12),
                     ha="center", fontsize=9, fontweight="bold", color=BLUE)

    # Impressions — right axis (green)
    ax2 = ax1.twinx()
    ax2.plot(labels, imp_data, color=GREEN, linewidth=2.5, marker="s",
             markersize=9, linestyle="--", label="Impressions", zorder=5)
    ax2.fill_between(labels, imp_data, alpha=0.08, color=GREEN)
    ax2.set_ylabel("Impressions", color=GREEN, fontsize=10)
    ax2.tick_params(axis="y", labelcolor=GREEN, labelsize=9)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color("#DADCE0")
    ax2.grid(False)
    for i, (lbl, val) in enumerate(zip(labels, imp_data)):
        ax2.annotate(f"{val:,}", (lbl, val),
                     textcoords="offset points", xytext=(0, -16),
                     ha="center", fontsize=9, fontweight="bold", color=GREEN)

    # Combined legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left")
    _title(ax1, "Search Console Performance: Clicks vs Impressions")

    fig.tight_layout()
    path = out_dir / "gsc_clicks_impressions.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 2: Monthly Organic Sessions — line chart ───────────────────────────

def chart_traffic_organic_sessions(context: dict, out_dir: Path) -> Path:
    """
    Line chart showing monthly organic sessions trend from GA4.
    File: traffic_organic_sessions.png
    """
    domain = context["client"]["domain"]
    month  = context["report_month"]

    months_to_try = [_prev_month(_prev_month(month)), _prev_month(month), month]
    labels, sessions = [], []
    for mo in months_to_try:
        val = _organic_sessions_from_cache(domain, mo)
        if val > 0:
            labels.append(_month_label(mo))
            sessions.append(val)

    # Fallback to processed context data
    if len(sessions) < 2:
        t = context["traffic"]
        labels   = [_month_label(_prev_month(month)), _month_label(month)]
        sessions = [t["organic_sessions_prev"], t["organic_sessions"]]

    fig, ax = plt.subplots(figsize=(9, 4.5))

    ax.plot(labels, sessions, color=BLUE, linewidth=3, marker="o",
            markersize=10, zorder=5)
    ax.fill_between(labels, sessions, alpha=0.12, color=BLUE)

    # Value labels on each point
    y_max = max(sessions) * 1.3 if sessions else 100
    for lbl, val in zip(labels, sessions):
        ax.annotate(f"{val:,}", (lbl, val),
                    textcoords="offset points", xytext=(0, 14),
                    ha="center", fontsize=11, fontweight="bold", color=BLUE)

    # Month-over-month growth badge (top right)
    if len(sessions) >= 2 and sessions[-2] > 0:
        pct = (sessions[-1] - sessions[-2]) / sessions[-2] * 100
        badge_color = GREEN if pct >= 0 else RED
        badge_bg    = LIGHT_GREEN if pct >= 0 else "#FDECEA"
        sign        = "+" if pct >= 0 else ""
        ax.text(0.98, 0.95, f"{sign}{pct:.1f}% MoM",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=12, fontweight="bold", color=badge_color,
                bbox=dict(boxstyle="round,pad=0.4", facecolor=badge_bg, edgecolor="none"))

    ax.set_ylabel("Organic Sessions", fontsize=10)
    ax.set_ylim(0, y_max)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    _title(ax, "Monthly Organic Sessions (Google Analytics 4)")

    fig.tight_layout()
    path = out_dir / "traffic_organic_sessions.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 3: Traffic by channel — donut chart ─────────────────────────────────

def chart_traffic_channels(context: dict, out_dir: Path) -> Path:
    """
    Donut chart of GA4 sessions by traffic channel.
    File: traffic_channels.png
    """
    channels = context["traffic"]["top_channels"]
    total    = sum(c["sessions"] for c in channels) or 1

    main, other = [], 0
    for c in channels:
        if c["sessions"] / total >= 0.03:
            main.append(c)
        else:
            other += c["sessions"]
    if other:
        main.append({"channel": "Other", "sessions": other})

    labels  = [c["channel"] for c in main]
    sizes   = [c["sessions"] for c in main]
    colors  = PIE_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(9, 5))
    wedges, _, autotexts = ax.pie(
        sizes, labels=None, colors=colors,
        autopct=lambda p: f"{p:.1f}%" if p >= 4 else "",
        startangle=140, pctdistance=0.72,
        wedgeprops={"edgecolor": "white", "linewidth": 2, "width": 0.55},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")
        at.set_fontweight("bold")

    # Centre label
    ax.text(0, 0, f"{total:,}\nSessions", ha="center", va="center",
            fontsize=11, fontweight="bold", color="#202124")

    legend_labels = [f"{l}  ({s:,})" for l, s in zip(labels, sizes)]
    ax.legend(wedges, legend_labels, loc="center left",
              bbox_to_anchor=(1.0, 0.5))
    _title(ax, "Traffic by Channel (Google Analytics 4)")

    fig.tight_layout()
    path = out_dir / "traffic_channels.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 4: Keyword ranking distribution ─────────────────────────────────────

def chart_keyword_distribution(context: dict, out_dir: Path) -> Path:
    """
    Left: bar chart of keyword counts by position band (Top 3 / 4-10 / 11-20 / 21+).
    Right: donut showing Top 3 vs rest.
    File: keyword_distribution.png
    """
    domain = context["client"]["domain"]
    month  = context["report_month"]
    rows   = _load_gsc_cache(domain, month)

    if rows:
        top3     = sum(1 for r in rows if r["position"] <= 3)
        pos4_10  = sum(1 for r in rows if 3  < r["position"] <= 10)
        pos11_20 = sum(1 for r in rows if 10 < r["position"] <= 20)
        pos21p   = sum(1 for r in rows if r["position"] > 20)
    else:
        k = context["keywords"]
        top3     = k["keywords_in_top_3"]
        pos4_10  = max(0, k["keywords_in_top_10"] - top3)
        pos11_20 = 0
        pos21p   = max(0, k["total_keywords_tracked"] - k["keywords_in_top_10"])

    bands  = ["Top 3\n(Pos 1-3)", "Top 10\n(Pos 4-10)", "Top 20\n(Pos 11-20)", "Pos 21+"]
    counts = [top3, pos4_10, pos11_20, pos21p]
    colors = [GREEN, BLUE, ORANGE, GREY]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

    # --- Bar chart ---
    bars = ax1.bar(bands, counts, color=colors, alpha=0.88, width=0.55, zorder=3)
    max_c = max(counts) if counts else 1
    ax1.set_ylim(0, max_c * 1.30)
    ax1.set_ylabel("Number of Keywords", fontsize=10)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: str(int(x))))
    ax1.grid(axis="y", zorder=0)
    ax1.grid(axis="x", visible=False)
    for bar in bars:
        val = int(bar.get_height())
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max_c * 0.025,
                 str(val), ha="center", va="bottom",
                 fontsize=12, fontweight="bold", color="#202124")
    _title(ax1, "Keyword Count by Position Band")

    # --- Donut chart ---
    nonzero = [(b, c, col) for b, c, col in zip(bands, counts, colors) if c > 0]
    if nonzero:
        pie_labels = [x[0].replace("\n", " ") for x in nonzero]
        pie_vals   = [x[1] for x in nonzero]
        pie_colors = [x[2] for x in nonzero]
        total_kw   = sum(pie_vals)

        wedges, _, autotexts = ax2.pie(
            pie_vals, labels=None, colors=pie_colors,
            autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
            startangle=90, pctdistance=0.70,
            wedgeprops={"edgecolor": "white", "linewidth": 2, "width": 0.5},
        )
        for at in autotexts:
            at.set_fontsize(9)
            at.set_fontweight("bold")
            at.set_color("white")
        ax2.text(0, 0, f"{total_kw}\nKeywords", ha="center", va="center",
                 fontsize=11, fontweight="bold", color="#202124")
        ax2.legend(wedges, [f"{l}: {v}" for l, v in zip(pie_labels, pie_vals)],
                   loc="center left", bbox_to_anchor=(0.85, 0.5))
        _title(ax2, "Keyword Distribution")
    else:
        ax2.text(0.5, 0.5, "No keyword data available",
                 ha="center", va="center", transform=ax2.transAxes, color=GREY)
        ax2.axis("off")

    fig.tight_layout()
    path = out_dir / "keyword_distribution.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 5: Keyword ranking positions — top keywords compared ────────────────

def chart_keyword_ranking_trend(context: dict, out_dir: Path) -> Path:
    """
    Grouped bar: previous vs current avg position for top keywords.
    File: keyword_ranking_trend.png
    """
    domain = context["client"]["domain"]
    month  = context["report_month"]
    prev   = _prev_month(month)

    curr_rows = _load_gsc_cache(domain, month)
    prev_rows = _load_gsc_cache(domain, prev)
    curr_map  = {r["keyword"]: r["position"] for r in curr_rows}
    prev_map  = {r["keyword"]: r["position"] for r in prev_rows}

    top_kws   = [kw["keyword"] for kw in context["keywords"]["top_by_clicks"][:10]]
    plot_kws  = [kw for kw in top_kws if kw in curr_map and kw in prev_map][:7]
    if not plot_kws:
        plot_kws = list(curr_map.keys())[:7]

    curr_pos  = [round(curr_map[kw], 1) for kw in plot_kws]
    prev_pos  = [round(prev_map.get(kw, curr_map[kw]), 1) for kw in plot_kws]
    labels    = [kw[:30] + "…" if len(kw) > 30 else kw for kw in plot_kws]

    x     = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, prev_pos, width, label=_month_label(prev), color=GREY, alpha=0.70)
    bars2 = ax.bar(x + width / 2, curr_pos, width, label=_month_label(month), color=BLUE, alpha=0.90)

    ax.invert_yaxis()
    ax.set_ylabel("Average Position (lower = better)", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=28, ha="right", fontsize=8)
    ax.legend()
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)

    for bar in bars2:
        val = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.3,
                f"{val:.1f}", ha="center", va="top", fontsize=7, color=BLUE)

    _title(ax, "Keyword Ranking Positions: Previous vs Current Month")
    fig.tight_layout()
    path = out_dir / "keyword_ranking_trend.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 6: Top queries by organic clicks ────────────────────────────────────

def chart_top_landing_pages(context: dict, out_dir: Path) -> Path:
    """
    Horizontal bar: top queries ranked by organic click volume.
    File: top_landing_pages.png
    """
    top    = context["keywords"]["top_by_clicks"][:8]
    labels = [kw["keyword"][:40] + "…" if len(kw["keyword"]) > 40 else kw["keyword"]
              for kw in top]
    clicks = [kw["clicks"] for kw in top]
    colors = [BLUE if i % 2 == 0 else "#4285F4" for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels[::-1], clicks[::-1], color=colors[::-1], alpha=0.88, height=0.55)

    max_c = max(clicks) if clicks else 1
    ax.set_xlim(0, max_c * 1.20)
    for bar in bars:
        _annotate_hbar(ax, bar)

    ax.set_xlabel("Organic Clicks", fontsize=10)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    _title(ax, "Top Queries by Organic Clicks (Source: Google Search Console)")

    fig.tight_layout()
    path = out_dir / "top_landing_pages.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 7: Engagement metrics — bounce rate + session duration ──────────────

def chart_engagement_metrics(context: dict, out_dir: Path) -> Path:
    """
    Two-panel bar: bounce rate and avg session duration, current vs previous month.
    File: engagement_metrics.png
    """
    domain = context["client"]["domain"]
    month  = context["report_month"]
    prev   = _prev_month(month)
    t      = context["traffic"]

    curr_ch = _load_ga4_cache(domain, month)
    prev_ch = _load_ga4_cache(domain, prev)

    def weighted(channels, metric):
        total = sum(c["sessions"] for c in channels.values()) or 1
        return sum(c[metric] * c["sessions"] for c in channels.values()) / total

    curr_bounce   = weighted(curr_ch, "bounce_rate")   if curr_ch else t["bounce_rate"]
    prev_bounce   = weighted(prev_ch, "bounce_rate")   if prev_ch else t["bounce_rate"]
    curr_dur      = weighted(curr_ch, "avg_session_duration_sec") if curr_ch else t["avg_session_duration_sec"]
    prev_dur      = weighted(prev_ch, "avg_session_duration_sec") if prev_ch else t["avg_session_duration_sec"]

    month_labels  = [_month_label(prev), _month_label(month)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # Bounce rate
    b_vals   = [round(prev_bounce, 1), round(curr_bounce, 1)]
    b_colors = [GREY, RED if curr_bounce > prev_bounce else GREEN]
    b1 = ax1.bar(month_labels, b_vals, color=b_colors, alpha=0.85, width=0.45)
    ax1.set_ylabel("Bounce Rate (%)", fontsize=10)
    ax1.set_ylim(0, max(b_vals) * 1.35 if b_vals else 100)
    ax1.grid(axis="y")
    ax1.grid(axis="x", visible=False)
    for bar in b1:
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max(b_vals) * 0.03,
                 f"{bar.get_height():.1f}%",
                 ha="center", fontsize=11, fontweight="bold", color="#202124")
    _title(ax1, "Bounce Rate")

    # Avg session duration
    d_vals   = [round(prev_dur, 0), round(curr_dur, 0)]
    d_colors = [GREY, GREEN if curr_dur >= prev_dur else RED]
    b2 = ax2.bar(month_labels, d_vals, color=d_colors, alpha=0.85, width=0.45)
    ax2.set_ylabel("Seconds", fontsize=10)
    ax2.set_ylim(0, max(d_vals) * 1.35 if d_vals else 300)
    ax2.grid(axis="y")
    ax2.grid(axis="x", visible=False)
    for bar in b2:
        s = int(bar.get_height())
        lbl = f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max(d_vals) * 0.03,
                 lbl, ha="center", fontsize=11, fontweight="bold", color="#202124")
    _title(ax2, "Avg Session Duration")

    fig.suptitle("Engagement Metrics: Month over Month",
                 fontsize=13, fontweight="bold", color="#202124", y=1.02)
    fig.tight_layout()
    path = out_dir / "engagement_metrics.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 8: Goal performance — target vs actual ──────────────────────────────

def chart_goal_performance(context: dict, out_dir: Path) -> Path:
    """
    Grouped bar: target vs actual for organic sessions, top 10 keywords, backlinks.
    File: goal_performance.png
    """
    targets = context.get("targets", {})
    t, k, b = context["traffic"], context["keywords"], context["backlinks"]

    metrics = [
        ("Organic\nSessions",  targets.get("organic_sessions_goal", 0), t["organic_sessions"]),
        ("Top 10\nKeywords",   targets.get("top_10_keywords_goal", 0),  k["keywords_in_top_10"]),
        ("New\nBacklinks",     targets.get("new_backlinks_goal", 0),     b["new_backlinks_count"]),
    ]

    labels      = [m[0] for m in metrics]
    target_vals = [m[1] for m in metrics]
    actual_vals = [m[2] for m in metrics]
    bar_colors  = [GREEN if a >= tgt else RED for a, tgt in zip(actual_vals, target_vals)]

    x     = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, target_vals, width, label="Target", color=GREY, alpha=0.55, zorder=3)
    bars = ax.bar(x + width / 2, actual_vals, width, label="Actual",
                  color=bar_colors, alpha=0.90, zorder=3)

    max_v = max(max(target_vals), max(actual_vals)) if actual_vals else 1
    ax.set_ylim(0, max_v * 1.30)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend()
    ax.grid(axis="y", zorder=0)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    for bar, color in zip(bars, bar_colors):
        val = int(bar.get_height())
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max_v * 0.025,
                f"{val:,}", ha="center", fontsize=10,
                fontweight="bold", color=color)

    _title(ax, "Goal Performance: Target vs Actual")
    fig.tight_layout()
    path = out_dir / "goal_performance.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 9: Backlinks overview — new/lost + dofollow breakdown ───────────────

def chart_backlinks_overview(context: dict, out_dir: Path) -> Path:
    """
    Left panel: new vs lost backlinks.
    Right panel: dofollow vs nofollow split for new links.
    File: backlink_overview.png
    """
    b       = context["backlinks"]
    new_bl  = b["new_backlinks_count"]
    lost_bl = b["lost_backlinks_count"]
    do_new  = b.get("dofollow_new", 0)
    nf_new  = max(0, new_bl - do_new)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # New vs Lost
    cats   = ["New Backlinks", "Lost Backlinks"]
    vals   = [new_bl, lost_bl]
    bcolors = [GREEN, RED]
    b1 = ax1.bar(cats, vals, color=bcolors, alpha=0.88, width=0.45, zorder=3)
    max_v = max(vals) if vals else 1
    ax1.set_ylim(0, max_v * 1.35)
    ax1.grid(axis="y", zorder=0)
    ax1.grid(axis="x", visible=False)
    for bar in b1:
        val = int(bar.get_height())
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max_v * 0.04,
                 str(val), ha="center", fontsize=14,
                 fontweight="bold", color="#202124")
    _title(ax1, "New vs Lost Backlinks")

    # Dofollow breakdown for new links
    if new_bl > 0:
        pie_vals   = [do_new, nf_new]
        pie_labels = [f"Dofollow ({do_new})", f"Nofollow ({nf_new})"]
        pie_colors = [GREEN, GREY]
        wedges, _, autotexts = ax2.pie(
            pie_vals, labels=None, colors=pie_colors,
            autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
            startangle=90, pctdistance=0.70,
            wedgeprops={"edgecolor": "white", "linewidth": 2, "width": 0.55},
        )
        for at in autotexts:
            at.set_fontsize(10)
            at.set_fontweight("bold")
            at.set_color("white")
        ax2.text(0, 0, f"{new_bl}\nNew Links", ha="center", va="center",
                 fontsize=11, fontweight="bold", color="#202124")
        ax2.legend(wedges, pie_labels, loc="lower center",
                   bbox_to_anchor=(0.5, -0.08))
    else:
        ax2.text(0.5, 0.5, "No new backlinks\nthis month",
                 ha="center", va="center", transform=ax2.transAxes,
                 fontsize=12, color=GREY)
        ax2.axis("off")
    _title(ax2, "New Links: Dofollow vs Nofollow")

    fig.tight_layout()
    path = out_dir / "backlink_overview.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Chart 10: CTR by top keywords ─────────────────────────────────────────────

def chart_ctr_top_keywords(context: dict, out_dir: Path) -> Path:
    """
    Horizontal bar chart of click-through rate for the top 8 keywords.
    File: ctr_top_keywords.png
    """
    top    = context["keywords"]["top_by_clicks"][:8]
    labels = [kw["keyword"][:34] + "…" if len(kw["keyword"]) > 34 else kw["keyword"]
              for kw in top]
    ctrs   = [kw["ctr"] for kw in top]
    colors = [GREEN if c >= 3 else BLUE if c >= 1 else ORANGE for c in ctrs]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels[::-1], ctrs[::-1], color=colors[::-1], alpha=0.88, height=0.55)

    max_c = max(ctrs) if ctrs else 1
    ax.set_xlim(0, max_c * 1.22)
    for bar in bars:
        w = bar.get_width()
        ax.text(w + max_c * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{w:.1f}%", va="center", fontsize=8, color=GREY)

    # Benchmark line at 3%
    if max_c > 3:
        ax.axvline(x=3, color=ORANGE, linestyle="--", linewidth=1.2, alpha=0.7)
        ax.text(3 + max_c * 0.01, 0.02, "3% benchmark",
                transform=ax.get_xaxis_transform(), fontsize=7,
                color=ORANGE, va="bottom")

    ax.set_xlabel("Click-Through Rate (%)", fontsize=10)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    _title(ax, "Click-Through Rate by Top Keywords (Source: GSC)")

    fig.tight_layout()
    path = out_dir / "ctr_top_keywords.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Chart saved: %s", path)
    return path


# ── Public entry point ────────────────────────────────────────────────────────

def generate_all_charts(context: dict, client_id: str) -> dict:
    """
    Generate all 10 SEO charts from real GA4 and GSC data.
    Returns dict mapping chart name -> Path.

    Chart files saved to: charts/<client_id>/<month>/
    """
    month   = context["report_month"]
    out_dir = _out_dir(client_id, month)
    log.info("Generating charts for %s / %s ...", client_id, month)

    charts = {
        # Search Console
        "clicks_impressions":  chart_gsc_clicks_impressions(context, out_dir),
        "ctr_keywords":        chart_ctr_top_keywords(context, out_dir),
        # GA4 Traffic
        "traffic_organic":     chart_traffic_organic_sessions(context, out_dir),
        "traffic_channels":    chart_traffic_channels(context, out_dir),
        # Keywords
        "keyword_distribution": chart_keyword_distribution(context, out_dir),
        "keyword_rankings":    chart_keyword_ranking_trend(context, out_dir),
        # Engagement & Business
        "engagement":          chart_engagement_metrics(context, out_dir),
        "goal_performance":    chart_goal_performance(context, out_dir),
        "top_pages":           chart_top_landing_pages(context, out_dir),
        # Backlinks
        "backlink_overview":   chart_backlinks_overview(context, out_dir),
    }

    log.info("All %d charts generated.", len(charts))
    return charts
