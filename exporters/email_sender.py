"""
Exporter: Email Delivery
Sends the report link to client contacts after pipeline completes.
Configure in .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM
Configure in config.yaml: report.email_recipients, report.send_email
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def _format_month(month_str: str) -> str:
    return datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")


def send_report_email(config: dict, report_url: str, month: str) -> bool:
    """
    Sends a report-ready email to all recipients listed in config.
    Returns True on success, False on failure. Never raises.
    """
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    email_from = os.environ.get("EMAIL_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        log.warning("Email not configured — skipping. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env")
        return False

    recipients = config.get("report", {}).get("email_recipients", [])
    if not recipients:
        log.warning("No email_recipients in config — skipping email.")
        return False

    client_name  = config["client"]["name"]
    month_display = _format_month(month)
    subject = f"SEO Report Ready: {client_name} — {month_display}"

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #1a1a2e; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #0f172a, #1e3a5f); padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 24px;">
            <p style="color: rgba(255,255,255,0.7); letter-spacing: 2px; text-transform: uppercase; font-size: 12px; margin: 0 0 8px 0;">Growleads Agency</p>
            <h1 style="color: white; font-size: 22px; margin: 0;">SEO Monthly Report Ready</h1>
            <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0 0;">{client_name} &nbsp;|&nbsp; {month_display}</p>
        </div>

        <p>Your monthly SEO report for <strong>{month_display}</strong> has been generated and is ready to view.</p>

        <div style="text-align: center; margin: 28px 0;">
            <a href="{report_url}"
               style="background: #2563eb; color: white; padding: 14px 32px; border-radius: 6px;
                      text-decoration: none; font-weight: bold; font-size: 15px;">
                View Report
            </a>
        </div>

        <p style="color: #64748b; font-size: 13px;">Or copy this link:<br>
            <a href="{report_url}" style="color: #2563eb;">{report_url}</a>
        </p>

        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">
            Report prepared by Growleads Agency &nbsp;|&nbsp; {month_display}
        </p>
    </body></html>
    """

    text_body = (
        f"SEO Monthly Report Ready\n\n"
        f"Client: {client_name}\n"
        f"Month: {month_display}\n\n"
        f"Your report is ready: {report_url}\n\n"
        f"Prepared by Growleads Agency"
    )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = email_from
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())

        log.info("Report email sent to: %s", ", ".join(recipients))
        return True

    except Exception as e:
        log.warning("Failed to send report email: %s", e)
        return False
