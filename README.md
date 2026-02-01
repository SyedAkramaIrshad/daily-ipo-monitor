# Daily IPO Monitor

I built this small automation to check the U.S. IPO calendar each morning (Dubai time) and email myself the tickers that meet a size threshold. It pulls same-day IPOs from Finnhub, filters U.S. exchanges, calculates offer amount (price x shares), and sends a summary email.

## What it checks
- Same-day IPOs only (Dubai date)
- U.S. exchanges: NASDAQ, NYSE, AMEX
- Offer amount >= USD 200M

## Schedule
Runs every day at 9:00 AM Dubai time via GitHub Actions. GitHub schedules are UTC, so the cron is set to 05:00 UTC.

## Setup (GitHub Actions)
1) Create a Finnhub API key.
2) Create a Gmail app password (or switch SMTP settings in `ipo_monitor.py`).
3) Add the following secrets in the repo settings:
   - FINNHUB_API_KEY
   - EMAIL_USER
   - EMAIL_APP_PASSWORD
   - EMAIL_TO

## Run locally
1) Create a `.env` file (see `.env.example`).
2) Install dependencies:
   `pip install -r requirements.txt`
3) Run:
   `python ipo_monitor.py`

## Verification
- Use the Actions tab to run the workflow manually, then attach a screenshot of the run and the email received.
