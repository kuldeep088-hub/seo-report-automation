"""
Exporter: PDF
Renders Jinja2 HTML template → PDF using xhtml2pdf (pure Python, no native deps).
"""

import base64
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
REPORTS_DIR = Path("reports")


def _format_month_display(month_str: str) -> str:
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.strftime("%B %Y")


def _commas(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _chart_to_base64(path) -> str:
    """Return a data URI for embedding a PNG chart directly in HTML."""
    try:
        data = Path(path).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode()
    except Exception:
        return ""


def export_pdf(context: dict, sections: dict, client_id: str, month: str,
               charts: dict = None) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["commas"] = _commas

    template = env.get_template("report_template.html")

    # Convert chart file paths to base64 data URIs for PDF embedding
    chart_images = {}
    if charts:
        for name, path in charts.items():
            if path and Path(path).exists():
                chart_images[name] = _chart_to_base64(path)

    html_content = template.render(
        client=context["client"],
        report_month=month,
        report_month_display=_format_month_display(month),
        traffic=context["traffic"],
        keywords=context["keywords"],
        backlinks=context["backlinks"],
        targets=context["targets"],
        sections=sections,
        chart_images=chart_images,
    )

    safe_month = month.replace("-", "_")
    pdf_filename = f"{client_id}_seo_report_{safe_month}.pdf"
    pdf_path = REPORTS_DIR / pdf_filename

    log.info("Rendering PDF: %s", pdf_path)
    with open(pdf_path, "wb") as pdf_file:
        result = pisa.CreatePDF(html_content.encode("utf-8"), dest=pdf_file)

    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} error(s)")

    return pdf_path
