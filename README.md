# SEO Report Automation

Automated monthly SEO reports powered by Claude AI.
Pulls data from GA4, Google Search Console, and Ahrefs, generates a fully formatted Google Doc report with tables and charts, and saves it to Google Drive — automatically on the 1st of every month.

---

## Features

- Collects data from **Google Analytics 4**, **Google Search Console**, and **Ahrefs**
- Reads **blog posts** and **business listings** from Google Sheets
- Writes AI-generated report sections using **Claude (Anthropic)**
- Generates **5 charts** (traffic trends, channel breakdown, keyword rankings, engagement, top pages)
- Creates a styled **Google Doc** with tables, charts, and branded headings
- Saves to **Google Drive** under `SEO Reports / CLIENT NAME / SEO_Monthly_Report_CLIENT_Month_Year`
- Runs automatically on the **1st of every month at 09:00** via the built-in scheduler

---

## Project Structure

```
report-automation/
├── clients/               # One folder per client
│   └── example_client/    # Copy this to add a new client
├── collectors/            # API data fetchers (GA4, GSC, Ahrefs, Sheets)
├── processors/            # Data normalizers and MoM calculators
├── ai/                    # Claude report writer and prompt templates
├── charts/                # Chart generator (matplotlib)
├── exporters/             # Google Docs exporter
├── logs/                  # Run logs (auto-created)
├── main.py                # Pipeline entry point
├── scheduler.py           # Monthly automation
└── setup_oauth.py         # One-time Google OAuth setup
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Required keys:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `AHREFS_API_KEY` — from app.ahrefs.com/api (optional — skipped if not set)

### 3. Set up Google OAuth

Google OAuth is used for Docs, Drive, and Sheets access.

1. Go to **Google Cloud Console** → APIs & Services → Credentials
2. Enable these APIs: **Google Analytics Data API**, **Search Console API**, **Google Docs API**, **Google Drive API**, **Google Sheets API**
3. Create an **OAuth 2.0 Client ID** (Desktop app) → download JSON → save as `credentials/oauth_client.json`
4. Run the one-time setup:
   ```bash
   python setup_oauth.py
   ```
5. A browser window opens — sign in and grant access. Token saved to `credentials/oauth_token.json`.

Also add your Google account as a **Viewer** in GA4 and GSC for each client property.

### 4. Add a client

1. Copy `clients/example_client/` to `clients/your_client_name/`
2. Edit `config.yaml`:

```yaml
client:
  name: "Client Display Name"
  domain: "example.com"
  ga4_property_id: "123456789"
  gsc_site_url: "https://example.com"
  ahrefs_target: "example.com"

targets:
  organic_sessions_goal: 5000
  new_backlinks_goal: 10
  top_10_keywords_goal: 20

report:
  output_format:
    - gdocs
  gdocs_folder_id: "YOUR_GOOGLE_DRIVE_FOLDER_ID"   # "SEO Reports" parent folder
  google_sheet_blog_id: "YOUR_SHEET_ID"             # Sheet with blog post tabs
  google_sheet_listings_id: "YOUR_SHEET_ID"         # Sheet with business listing tabs
```

**Google Sheets tab format:** Each sheet should have monthly tabs named e.g. `February Backlinks` or `February 2026`. Columns: `Platform` | `Link`.

---

## Running

### Generate a report for one client

```bash
python main.py --client your_client_name --month 2025-03
```

### Run all clients immediately (previous month)

```bash
python scheduler.py --now
```

### Run a single client via the scheduler

```bash
python scheduler.py --client your_client_name
```

### Start the monthly auto-scheduler

```bash
python scheduler.py
```

Runs automatically on the **1st of each month at 09:00**, covering the previous calendar month.

---

## Output

A Google Doc is created and saved to:
```
SEO Reports / CLIENT NAME / SEO_Monthly_Report_CLIENT_March_2025
```

The document includes:
1. Executive Summary
2. Search Console Performance (table + chart)
3. GA4 Performance (tables + pie chart)
4. Engagement Quality (table + chart)
5. Business Impact / Goal Performance (table + chart)
6. Keyword Rankings (improved + declined tables + chart)
7. Backlinks Summary
8. Content Distribution (blog posts from Google Sheets)
9. Authority Building (business listings from Google Sheets)
10. Content Performance (top queries table)
11. Next Steps

---

## Scheduler Hosting Options

To run automatically without leaving your PC on, host the scheduler on:

- **GitHub Actions** (free) — use a cron workflow to run `python scheduler.py --now` on the 1st of each month
- **Oracle Cloud Free VM** — always-on Linux server, free forever
- **Google Cloud e2-micro** — free tier VM

---

## Adding More Clients

1. Copy `clients/example_client/` → `clients/new_client/`
2. Fill in `config.yaml`
3. Share GA4, GSC, and Google Sheets with your OAuth account
4. Run: `python scheduler.py --client new_client`
