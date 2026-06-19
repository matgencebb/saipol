"""colza-brief : génère et envoie un résumé quotidien (cours, actualités, météo)."""

import json
import os
import smtplib
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.message import EmailMessage

import requests
import yfinance as yf
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

load_dotenv()


TICKERS = {
    "rapeseed_matif": "RS=F",
    "soybean_oil": "ZL=F",
    "soybean_meal": "ZM=F",
}

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MAX_RETRIES = 4
GEMINI_RETRY_BASE_DELAY = 4

NEWS_QUERIES = {
    "colza_matif": "colza MATIF prix",
    "rapeseed": "rapeseed market",
    "canola": "canola price",
}
NEWS_PER_QUERY = 5
HTTP_TIMEOUT = 15

WEATHER_ZONES = {
    "UE (Bassin parisien)": {"latitude": 49.0, "longitude": 2.5},
    "Allemagne": {"latitude": 52.0, "longitude": 10.0},
    "Canada (Saskatchewan)": {"latitude": 52.0, "longitude": -106.0},
    "Ukraine (Kyiv)": {"latitude": 50.45, "longitude": 30.52},
    "Australie (WA)": {"latitude": -31.9, "longitude": 116.0},
}
WEATHER_FORECAST_DAYS = 3

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


def _fetch_news_feed(query, limit):
    """Récupère les derniers articles Google News (flux RSS) pour une requête."""
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": "fr", "gl": "FR", "ceid": "FR:fr"}

    try:
        response = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError) as exc:
        return {"query": query, "articles": [], "error": str(exc)}

    articles = []
    for item in root.findall(".//item")[:limit]:
        source = item.find("source")
        articles.append(
            {
                "title": item.findtext("title"),
                "link": item.findtext("link"),
                "published": item.findtext("pubDate"),
                "source": source.text if source is not None else None,
            }
        )

    return {"query": query, "articles": articles}


def get_news():
    """Récupère les actualités pertinentes via les flux RSS Google News.

    Couvre le colza MATIF, le rapeseed et le canola. Retourne un dict indexé
    par thème, chaque entrée contenant les articles récents (titre, lien,
    date, source).
    """
    return {
        theme: _fetch_news_feed(query, NEWS_PER_QUERY)
        for theme, query in NEWS_QUERIES.items()
    }


def _fetch_zone_weather(zone, coords):
    """Récupère les prévisions Open-Meteo pour une zone de production."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": WEATHER_FORECAST_DAYS,
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        daily = response.json().get("daily", {})
    except (requests.RequestException, ValueError) as exc:
        return {"zone": zone, "daily": [], "error": str(exc)}

    dates = daily.get("time", [])
    forecast = [
        {
            "date": dates[i],
            "temp_min": daily.get("temperature_2m_min", [])[i],
            "temp_max": daily.get("temperature_2m_max", [])[i],
            "precipitation_mm": daily.get("precipitation_sum", [])[i],
        }
        for i in range(len(dates))
    ]

    return {"zone": zone, "daily": forecast}


def get_weather():
    """Récupère les prévisions météo des zones de production via Open-Meteo.

    Couvre l'UE, le Canada, l'Ukraine et l'Australie (zones colza/canola).
    Retourne un dict indexé par zone avec les prévisions journalières
    (températures min/max, précipitations). API gratuite, sans clé.
    """
    return {
        zone: _fetch_zone_weather(zone, coords)
        for zone, coords in WEATHER_ZONES.items()
    }


def build_summary(prices=None, news=None, weather=None):
    """Génère le brief matinal via l'API Gemini.

    Agrège les données collectées (prix/spreads, actualités, météo des zones
    de production) et demande à Gemini de rédiger un brief structuré, factuel
    et orienté trading. Retourne le texte du brief.
    """
    payload = {
        "prix": prices,
        "news": news,
        "meteo": weather,
    }

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    user_content = (
        "Données du jour (format JSON) :\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
    )

    config = types.GenerateContentConfig(
        system_instruction=ANALYST_SYSTEM_PROMPT,
        max_output_tokens=4096,
    )

    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_content,
                config=config,
            )
            return response.text
        except genai_errors.ServerError:
            if attempt == GEMINI_MAX_RETRIES - 1:
                raise
            time.sleep(GEMINI_RETRY_BASE_DELAY * (2 ** attempt))


def send_email(summary, recipient=None):
    """Envoie le brief par email via le SMTP de Gmail.

    Utilise GMAIL_USER et GMAIL_APP_PASSWORD (mot de passe d'application).
    Le destinataire par défaut est l'expéditeur lui-même. Retourne True en
    cas de succès.
    """
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        raise RuntimeError(
            "GMAIL_USER et GMAIL_APP_PASSWORD doivent être définis dans l'environnement."
        )

    recipient = recipient or gmail_user
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    message = EmailMessage()
    message["Subject"] = f"Brief matinal colza — {today}"
    message["From"] = gmail_user
    message["To"] = recipient
    message.set_content(summary or "(brief vide)")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(message)

    return True


def main():
    prices = get_prices()
    news = get_news()
    weather = get_weather()
    summary = build_summary(prices=prices, news=news, weather=weather)
    send_email(summary)


if __name__ == "__main__":
    main()
