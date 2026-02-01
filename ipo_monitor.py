import os
import ssl
import smtplib
import requests
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
DUBAI_TZ_OFFSET = timedelta(hours=4)

# ------------------------------------------------------------------
# TIME
# ------------------------------------------------------------------
def today_dubai_iso() -> str:
    now_utc = datetime.now(timezone.utc)
    dubai_now = now_utc + DUBAI_TZ_OFFSET
    return dubai_now.strftime("%Y-%m-%d")

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
def parse_price(price_field: str) -> float | None:
    """
    Finnhub price is often '20-22'
    We conservatively take the max.
    """
    if not price_field:
        return None

    if "-" in price_field:
        low, high = price_field.split("-")
        return float(high.strip())

    return float(price_field)

def offer_amount_usd(ipo: dict) -> float | None:
    price = parse_price(ipo.get("price"))
    shares = ipo.get("numberOfShares")

    if price is None or shares is None:
        return None

    return price * float(shares)

def filter_large_us_ipos(ipos: list[dict]) -> list[dict]:
    results = []

    for ipo in ipos:
        exchange = (ipo.get("exchange") or "").upper()
        if exchange not in {"NASDAQ", "NYSE", "AMEX"}:
            continue

        amt = offer_amount_usd(ipo)
        if amt and amt >= MIN_OFFER_AMOUNT_USD:
            ipo["_offer_amount_usd"] = amt
            results.append(ipo)

    return results

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
        lines.append(
            f"- {ipo['symbol']} | {ipo['name']} | "
            f"USD {ipo['_offer_amount_usd']:,.0f}"
        )

    return "\n".join(lines)

# ------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------
def run():
    if not FINNHUB_API_KEY:
        raise RuntimeError("FINNHUB_API_KEY is missing")
    if not EMAIL_USER or not EMAIL_APP_PASSWORD or not EMAIL_TO:
        raise RuntimeError("EMAIL_USER/EMAIL_APP_PASSWORD/EMAIL_TO are missing")

    date_iso = today_dubai_iso()

    ipos = fetch_same_day_ipos(date_iso)

    us_ipos = []
    missing_data = 0
    for ipo in ipos:
        exchange = (ipo.get("exchange") or "").upper()
        if exchange not in {"NASDAQ", "NYSE", "AMEX"}:
            continue
        us_ipos.append(ipo)
        if offer_amount_usd(ipo) is None:
            missing_data += 1

    large_ipos = filter_large_us_ipos(ipos)
    stats = {
        "total_ipos": len(ipos),
        "us_ipos": len(us_ipos),
        "missing_data": missing_data,
        "qualified": len(large_ipos),
    }

    body = build_email(large_ipos, date_iso, stats)
    subject = f"IPO Monitor {date_iso} - {len(large_ipos)} qualifying IPO(s)"

    send_email(subject, body)
    print(subject)
    for i in large_ipos:
        print(i["symbol"])

if __name__ == "__main__":
    run()
