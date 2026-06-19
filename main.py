"""colza-brief : génère et envoie un résumé quotidien (cours, actualités, météo)."""

import os

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()


TICKERS = {
    "rapeseed_matif": "RS=F",
    "soybean_oil": "ZL=F",
    "soybean_meal": "ZM=F",
}


def _fetch_ticker(ticker):
    """Récupère le dernier cours et la variation sur 5 jours d'un ticker.

    Retourne un dict avec le cours courant, le cours d'il y a 5 jours,
    la variation absolue, la variation en pourcentage et la devise.
    """
    data = yf.Ticker(ticker)
    history = data.history(period="5d")

    if history.empty:
        return {
            "ticker": ticker,
            "last": None,
            "previous": None,
            "change": None,
            "change_pct": None,
            "currency": None,
            "error": "Aucune donnée disponible",
        }

    closes = history["Close"].dropna()
    last = float(closes.iloc[-1])
    previous = float(closes.iloc[0])
    change = last - previous
    change_pct = (change / previous * 100) if previous else None

    try:
        currency = data.fast_info.get("currency")
    except Exception:
        currency = None

    return {
        "ticker": ticker,
        "last": round(last, 2),
        "previous": round(previous, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "currency": currency,
    }


def get_prices():
    """Récupère les cours des actifs suivis via yfinance.

    Couvre le colza MATIF (RS=F) ainsi que l'huile (ZL=F) et le tourteau
    de soja (ZM=F) pour le contexte crush. Retourne un dict propre indexé
    par nom d'actif.
    """
    return {name: _fetch_ticker(ticker) for name, ticker in TICKERS.items()}


def get_news():
    """Récupère les actualités pertinentes."""
    pass


def get_weather():
    """Récupère les prévisions météo."""
    pass


def build_summary():
    """Construit le résumé à partir des données collectées."""
    pass


def send_email():
    """Envoie le résumé par email via Gmail."""
    pass


def main():
    prices = get_prices()
    news = get_news()
    weather = get_weather()
    summary = build_summary()
    send_email()


if __name__ == "__main__":
    main()
