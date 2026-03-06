"""
Processor: Backlinks
Structures and summarizes Ahrefs backlink data.
"""


def process_backlinks(raw: dict) -> dict:
    """
    Input:  raw dict from collectors/ahrefs.py
    Output: structured backlink summary
    """
    new_links = raw.get("new_backlinks", [])
    lost_links = raw.get("lost_backlinks", [])
    metrics = raw.get("domain_metrics", {})

    # Calculate average DR of new backlinks
    dr_values = [
        link.get("domain_rating_source", 0)
        for link in new_links
        if link.get("domain_rating_source", 0) > 0
    ]
    avg_dr_new = round(sum(dr_values) / len(dr_values), 1) if dr_values else 0

    # Dofollow vs nofollow split
    dofollow_new = [l for l in new_links if l.get("is_dofollow")]
    dofollow_lost = [l for l in lost_links if l.get("is_dofollow")]

    # Top new backlinks by DR
    top_new = sorted(new_links, key=lambda x: x.get("domain_rating_source", 0), reverse=True)[:10]

    # Domain metrics from Ahrefs
    domain_rating = metrics.get("domain_rating", "N/A")
    total_backlinks = metrics.get("backlinks", "N/A")
    referring_domains = metrics.get("referring_domains", "N/A")

    return {
        "month": raw["month"],
        "new_backlinks_count": len(new_links),
        "lost_backlinks_count": len(lost_links),
        "dofollow_new": len(dofollow_new),
        "dofollow_lost": len(dofollow_lost),
        "avg_dr_new_backlinks": avg_dr_new,
        "domain_rating": domain_rating,
        "total_backlinks": total_backlinks,
        "referring_domains": referring_domains,
        "top_new_backlinks": top_new,
        "lost_backlinks_sample": lost_links[:5],
    }
