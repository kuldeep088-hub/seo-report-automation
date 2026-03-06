# SEO Report Automation

An automated system that generates fully formatted monthly SEO reports using real data from Google Analytics 4, Google Search Console, and Google Sheets — written and styled by Claude AI, then saved directly to Google Docs.

---

## Project Overview

This system runs on the 1st of every month and produces a complete SEO report for each configured client. It collects data from multiple sources, generates AI-written insights, builds charts, and exports everything into a branded Google Doc saved in Google Drive.

**Data sources:**
- **Google Analytics 4** — sessions, traffic channels, new users, engagement metrics
- **Google Search Console** — clicks, impressions, keyword rankings, CTR
- **Google Sheets** — blog posts and business listings submitted that month
- **Ahrefs** — domain rating, backlinks, referring domains (optional)
- **Claude AI** — writes executive summary, analysis sections, and next steps
- **Google Docs** — final formatted report with tables and charts

---

## Features

- Automatic monthly report generation (runs on the 1st of every month at 09:00)
- GA4 traffic analysis with month-over-month comparison
- Google Search Console keyword and click data
- 5 auto-generated charts (traffic trends, channel breakdown, keyword rankings, engagement, top pages)
- Blog posts and business listings pulled from Google Sheets
- AI-generated executive summary, analysis, and recommendations via Claude
- Fully formatted Google Doc with branded headings, tables, and embedded charts
- Reports saved to Google Drive under `SEO Reports / CLIENT NAME /`
- Multi-client support — add as many clients as needed
- Per-run log files for easy debugging

---

## Project Structure

```
seo-report-automation/
│
├── main.py                  # Main pipeline — runs all phases for one client
├── scheduler.py             # Monthly automation scheduler
├── setup_oauth.py           # One-time Google OAuth setup script
├── test_connections.py      # Test that all API connections are working
│
├── clients/                 # One folder per client
│   ├── example_client/      # Template — copy this to add a new client
│   │   ├── config.yaml      # Client settings (GA4 ID, GSC URL, Sheet IDs, etc.)
│   │   └── work_log.md      # Monthly notes about what work was done
│   └── your_client/
│       ├── config.yaml
│       └── work_log.md
│
├── collectors/              # Fetches raw data from APIs
│   ├── google_analytics.py  # GA4 data collector
│   ├── search_console.py    # Google Search Console collector
│   ├── ahrefs.py            # Ahrefs backlink collector
│   └── sheets_collector.py  # Google Sheets collector (blog posts & listings)
│
├── processors/              # Cleans and processes raw API data
│   ├── traffic.py           # GA4 data processing and MoM comparison
│   ├── keywords.py          # Keyword ranking analysis
│   └── backlinks.py         # Backlink metrics processing
│
├── ai/                      # Claude AI report writer
│   ├── report_writer.py     # Generates all written sections using Claude
│   └── prompts/             # Prompt templates for each report section
│
├── charts/                  # Chart generation
│   └── chart_generator.py   # Creates 5 matplotlib charts per report
│
├── exporters/               # Report exporters
│   ├── gdocs_exporter.py    # Creates and formats the Google Doc
│   └── pdf_exporter.py      # Optional PDF export
│
├── credentials/             # Google credentials (NOT committed to git)
│   ├── oauth_client.json    # Downloaded from Google Cloud Console
│   ├── oauth_token.json     # Auto-generated after running setup_oauth.py
│   └── google_service_account.json  # Optional service account key
│
├── .env                     # Your API keys (NOT committed to git)
├── .env.example             # Template showing required environment variables
└── requirements.txt         # Python dependencies
```

---

## Setup Instructions

### Step 1 — Clone the repository

```bash
git clone https://github.com/kuldeep088-hub/seo-report-automation.git
cd seo-report-automation
```

### Step 2 — Install Python dependencies

Requires Python 3.9 or higher.

```bash
pip install -r requirements.txt
```

### Step 3 — Create your `.env` file

Copy the example file and fill in your API keys:

```bash
cp .env.example .env
```

Open `.env` and add your keys (see [Environment Variables](#environment-variables) section below).

### Step 4 — Enable Google APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Go to **APIs & Services → Library** and enable these APIs:
   - Google Analytics Data API
   - Google Search Console API
   - Google Drive API
   - Google Docs API
   - Google Sheets API

### Step 5 — Set up Google OAuth

OAuth allows the system to create Google Docs and read Google Sheets on your behalf.

1. In Google Cloud Console → **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Download the JSON file → save it as `credentials/oauth_client.json`
5. Run the one-time setup:

```bash
python setup_oauth.py
```

A browser window will open. Sign in with your Google account and grant access. This saves `credentials/oauth_token.json` which is used for all future runs.

> **Important:** The Google account you use here must have access to the GA4 property, GSC site, and Google Drive folder for each client.

### Step 6 — Add client access

For each client, share the following with your Google account (the one used in OAuth):

| Resource | Permission needed |
|---|---|
| GA4 Property | Viewer |
| Google Search Console | Restricted user |
| Google Sheets (blog & listings) | Viewer |
| Google Drive folder (for reports) | Editor |

### Step 7 — Configure a client

Copy the example client folder:

```bash
cp -r clients/example_client clients/your_client_name
```

Edit `clients/your_client_name/config.yaml`:

```yaml
client:
  name: "Your Client Name"
  domain: "example.com"
  ga4_property_id: "123456789"        # From GA4 Admin > Property Settings
  gsc_site_url: "https://example.com" # Exactly as it appears in Search Console
  ahrefs_target: "example.com"        # Optional — leave blank if not using Ahrefs

targets:
  organic_sessions_goal: 5000
  new_backlinks_goal: 10
  top_10_keywords_goal: 20

report:
  output_format:
    - gdocs
  gdocs_folder_id: "YOUR_GOOGLE_DRIVE_FOLDER_ID"    # The "SEO Reports" parent folder ID
  google_sheet_blog_id: "YOUR_BLOG_SHEET_ID"         # Google Sheet ID for blog posts
  google_sheet_listings_id: "YOUR_LISTINGS_SHEET_ID" # Google Sheet ID for business listings
```

**How to find the Google Drive folder ID:**
Open the folder in Google Drive. The ID is the last part of the URL:
`https://drive.google.com/drive/folders/THIS_IS_THE_FOLDER_ID`

**How to find the Google Sheet ID:**
Open the sheet. The ID is between `/d/` and `/edit` in the URL:
`https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit`

---

## Required APIs

| API | Used for |
|---|---|
| Google Analytics Data API | Fetching sessions, users, traffic channels |
| Google Search Console API | Fetching clicks, impressions, keyword rankings |
| Google Drive API | Creating folders and uploading chart images |
| Google Docs API | Creating and formatting the report document |
| Google Sheets API | Reading blog posts and business listings |
| Anthropic Claude API | Generating AI-written report sections |

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Anthropic Claude AI
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Ahrefs (optional — backlink data)
AHREFS_API_KEY=your_ahrefs_api_key_here

# Google credentials (paths to credential files)
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google_service_account.json
GOOGLE_OAUTH_TOKEN_FILE=credentials/oauth_token.json
```

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | From [console.anthropic.com](https://console.anthropic.com) |
| `AHREFS_API_KEY` | No | From app.ahrefs.com — skipped if not set |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | No | Path to service account JSON (fallback if OAuth not available) |
| `GOOGLE_OAUTH_TOKEN_FILE` | No | Path to OAuth token (default: `credentials/oauth_token.json`) |

---

## Google Sheet Format

Each Google Sheet should have tabs named by month, for example:
- `February Backlinks`
- `March Backlinks`
- or `February 2026`

The system does fuzzy tab matching — it will find the right tab as long as the month name is in the tab title.

Each tab must have these two columns (headers are flexible, case-insensitive):

| Platform | Link |
|---|---|
| Forbes | https://forbes.com/example |
| LinkedIn | https://linkedin.com/example |

The system detects `Platform` / `Site` / `Name` for the first column and `Link` / `URL` / `Href` for the second — so exact header names don't matter.

---

## Running the Project

### Test all connections first

```bash
python test_connections.py
```

### Generate a report for one client

```bash
python main.py --client scotle --month 2025-02
```

### Generate report for the current (previous) month

```bash
python main.py --client scotle
```

### Run all clients immediately

```bash
python scheduler.py --now
```

### Run a single client via the scheduler

```bash
python scheduler.py --client scotle
```

### Override the report month

```bash
python scheduler.py --client scotle --month 2026-01
```

### Start the monthly auto-scheduler

```bash
python scheduler.py
```

---

## Automation

The scheduler runs a daily check at 09:00. On the 1st of each month it automatically:

1. Detects the previous calendar month (e.g. runs on 1 March → generates February report)
2. Discovers all clients in the `clients/` folder
3. Runs the full pipeline for each client
4. Logs a summary with success/failure status and doc URLs

To keep it running in the background on a server:

```bash
nohup python scheduler.py &
```

Or use a process manager like `systemd`, `pm2`, or `supervisor`.

**To run it on GitHub Actions** (no server needed), create `.github/workflows/monthly_report.yml`:

```yaml
on:
  schedule:
    - cron: '0 9 1 * *'   # 1st of every month at 09:00 UTC
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scheduler.py --now
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

---

## Output

Each report is saved to Google Drive at:

```
SEO Reports / CLIENT NAME / SEO_Monthly_Report_CLIENT_Month_Year
```

Example:
```
SEO Reports / SCOTLE HIGH SCHOOL / SEO_Monthly_Report_SCOTLE_February_2026
```

The Google Doc contains 11 sections:

| # | Section |
|---|---|
| 1 | Executive Summary |
| 2 | Search Console Performance (table + chart) |
| 3 | GA4 Performance (traffic tables + pie chart) |
| 4 | Engagement Quality (table + chart) |
| 5 | Business Impact / Goal Performance (table + chart) |
| 6 | Keyword Rankings — improved and declined (tables + chart) |
| 7 | Backlinks Summary |
| 8 | Content Distribution (blog posts from Google Sheets) |
| 9 | Authority Building (business listings from Google Sheets) |
| 10 | Content Performance (top queries table) |
| 11 | Next Steps |

---

## Adding a New Client

1. Copy the example client folder:
   ```bash
   cp -r clients/example_client clients/new_client_name
   ```
2. Edit `clients/new_client_name/config.yaml` with the client's details
3. Share GA4, GSC, Sheets, and Drive folder access with your Google account
4. Test it:
   ```bash
   python main.py --client new_client_name --month 2026-02
   ```

The new client will be picked up automatically by the scheduler on the next run.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `invalid_scope: Bad Request` | Re-run `setup_oauth.py` — the token is missing a required scope |
| `Tab 'X' not found` | Check the sheet has a tab with the month name in the title |
| `storageQuotaExceeded` | Your Google Drive is full, or you are using a service account (use OAuth instead) |
| `AHREFS_API_KEY not set` | This is a warning, not an error — backlink section will show placeholder data |
| Charts not appearing | Check `charts/client/month/` folder exists and contains `.png` files |

---

## License

MIT
