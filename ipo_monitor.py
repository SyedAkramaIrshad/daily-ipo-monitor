import os
import ssl
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from dotenv import load_dotenv
load_dotenv()

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

FINNHUB_IPO_URL = "https://finnhub.io/api/v1/calendar/ipo"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO")

MIN_OFFER_AMOUNT_USD = 200_000_000
US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}
try:
    DUBAI_TZ = ZoneInfo("Asia/Dubai")
except ZoneInfoNotFoundError:
    DUBAI_TZ = timezone(timedelta(hours=4))

# ------------------------------------------------------------------
# TIME
# ------------------------------------------------------------------
def today_dubai_iso() -> str:
    return datetime.now(DUBAI_TZ).strftime("%Y-%m-%d")

# ------------------------------------------------------------------
# DATA FETCH
# ------------------------------------------------------------------
def fetch_same_day_ipos(date_iso: str) -> list[dict]:
    params = {
        "from": date_iso,
        "to": date_iso,
        "token": FINNHUB_API_KEY
    }

    resp = requests.get(FINNHUB_IPO_URL, params=params, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    return data.get("ipoCalendar", [])

# ------------------------------------------------------------------
# BUSINESS LOGIC
# ------------------------------------------------------------------
def parse_price(price_field: str | None) -> float | None:
    """
    Finnhub price is often '20-22'
    We conservatively take the max.
    """
    if not price_field:
        return None

    price_field = price_field.strip().replace("$", "").replace(",", "")
    if "-" in price_field:
        parts = [p.strip() for p in price_field.split("-") if p.strip()]
        if not parts:
            return None
        try:
            return float(parts[-1])
        except ValueError:
            return None

    try:
        return float(price_field)
    except ValueError:
        return None

def offer_amount_usd(ipo: dict) -> float | None:
    price = parse_price(ipo.get("price"))
    shares = ipo.get("numberOfShares")

    if price is None or shares is None:
        return None

    try:
        shares_value = float(str(shares).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
    if shares_value <= 0:
        return None

    return price * shares_value

def analyze_ipos(ipos: list[dict]) -> tuple[list[dict], dict]:
    stats = {
        "total_ipos": 0,
        "us_ipos": 0,
        "missing_data": 0,
        "qualified": 0,
    }
    qualified = []

    for ipo in ipos:
        stats["total_ipos"] += 1
        exchange = (ipo.get("exchange") or "").upper()
        if exchange not in US_EXCHANGES:
            continue

        stats["us_ipos"] += 1
        amt = offer_amount_usd(ipo)
        if amt is None:
            stats["missing_data"] += 1
            continue

        if amt >= MIN_OFFER_AMOUNT_USD:
            ipo["_offer_amount_usd"] = amt
            qualified.append(ipo)
            stats["qualified"] += 1

    return qualified, stats

# ------------------------------------------------------------------
# EMAIL
# ------------------------------------------------------------------
def send_email(subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_USER, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())

def build_email(ipos: list[dict], date_iso: str, stats: dict) -> str:
    summary_lines = [
        f"Date (Dubai): {date_iso}",
        f"Total IPOs returned: {stats['total_ipos']}",
        f"U.S. exchanges (NASDAQ/NYSE/AMEX): {stats['us_ipos']}",
        f"Missing price/shares: {stats['missing_data']}",
        f"Offer >= USD {MIN_OFFER_AMOUNT_USD:,}: {stats['qualified']}",
        ""
    ]

    if not ipos:
        return "\n".join(
            [
                f"No U.S. same-day IPOs with offer amount above "
                f"USD {MIN_OFFER_AMOUNT_USD:,}.",
                "",
            ]
            + summary_lines
        )

    lines = [
        f"U.S. Same-Day IPOs on {date_iso} (> USD 200M)",
        "",
        *summary_lines
    ]

    for ipo in ipos:
        symbol = ipo.get("symbol") or "UNKNOWN"
        name = ipo.get("name") or "Unknown"
        lines.append(
            f"- {symbol} | {name} | "
            f"USD {ipo['_offer_amount_usd']:,.0f}"
        )

    return "\n".join(lines)

# ------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------
def require_env() -> None:
    missing = []
    if not FINNHUB_API_KEY:
        missing.append("FINNHUB_API_KEY")
    if not EMAIL_USER:
        missing.append("EMAIL_USER")
    if not EMAIL_APP_PASSWORD:
        missing.append("EMAIL_APP_PASSWORD")
    if not EMAIL_TO:
        missing.append("EMAIL_TO")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

def run():
    require_env()

    date_iso = today_dubai_iso()

    ipos = fetch_same_day_ipos(date_iso)
    large_ipos, stats = analyze_ipos(ipos)

    body = build_email(large_ipos, date_iso, stats)
    subject = f"IPO Monitor {date_iso} - {len(large_ipos)} qualifying IPO(s)"

    send_email(subject, body)
    print(subject)
    for i in large_ipos:
        print(i["symbol"])

if __name__ == "__main__":
    run()
