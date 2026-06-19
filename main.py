"""colza-brief : génère et envoie un résumé quotidien (cours, actualités, météo)."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_prices():
    """Récupère les cours des actifs suivis."""
    pass


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
