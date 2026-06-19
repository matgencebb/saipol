"""colza-brief : génère et envoie un résumé quotidien (cours, actualités, météo)."""

import json
import os

import yfinance as yf
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


TICKERS = {
    "rapeseed_matif": "RS=F",
    "soybean_oil": "ZL=F",
    "soybean_meal": "ZM=F",
}

ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

ANALYST_SYSTEM_PROMPT = """Tu es analyste sur un desk de trading de colza. \
À partir des données fournies (prix, spreads, news, météo des zones de \
production), rédige un brief matinal en français, structuré ainsi :

1. Prix & mouvements clés (MATIF colza, contexte crush avec soyoil/soymeal)
2. Facteurs du jour (news, géopolitique, logistique)
3. Météo & récoltes (impact sur l'offre UE/Canada/Ukraine/Australie)
4. À surveiller aujourd'hui

Sois factuel, concis, orienté trading. Pas de blabla. Si une donnée manque, \
ne l'invente pas : signale-le brièvement."""


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


def build_summary(prices=None, news=None, weather=None):
    """Génère le brief matinal via l'API Anthropic.

    Agrège les données collectées (prix/spreads, actualités, météo des zones
    de production) et demande à Claude de rédiger un brief structuré, factuel
    et orienté trading. Retourne le texte du brief.
    """
    payload = {
        "prix": prices,
        "news": news,
        "meteo": weather,
    }

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_content = (
        "Données du jour (format JSON) :\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1500,
        system=ANALYST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )


def send_email():
    """Envoie le résumé par email via Gmail."""
    pass


def main():
    prices = get_prices()
    news = get_news()
    weather = get_weather()
    summary = build_summary(prices=prices, news=news, weather=weather)
    send_email()


if __name__ == "__main__":
    main()
