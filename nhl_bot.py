#!/usr/bin/env python3
"""Постит в Telegram расписание НХЛ на текущую ночь по московскому времени."""

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

MSK = ZoneInfo("Europe/Moscow")
NHL_API = "https://api-web.nhle.com/v1/schedule/{date}"

# Короткие русские названия. Аббревиатура остаётся, чтобы не путать NYR/NYI.
TEAMS = {
    "ANA": "Анахайм",
    "BOS": "Бостон",
    "BUF": "Баффало",
    "CAR": "Каролина",
    "CBJ": "Коламбус",
    "CGY": "Калгари",
    "CHI": "Чикаго",
    "COL": "Колорадо",
    "DAL": "Даллас",
    "DET": "Детройт",
    "EDM": "Эдмонтон",
    "FLA": "Флорида",
    "LAK": "Лос-Анджелес",
    "MIN": "Миннесота",
    "MTL": "Монреаль",
    "NJD": "Нью-Джерси",
    "NSH": "Нэшвилл",
    "NYI": "Айлендерс",
    "NYR": "Рейнджерс",
    "OTT": "Оттава",
    "PHI": "Филадельфия",
    "PIT": "Питтсбург",
    "SEA": "Сиэтл",
    "SJS": "Сан-Хосе",
    "STL": "Сент-Луис",
    "TBL": "Тампа",
    "TOR": "Торонто",
    "UTA": "Юта",
    "VAN": "Ванкувер",
    "VGK": "Вегас",
    "WPG": "Виннипег",
    "WSH": "Вашингтон",
}

MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def team_label(team: dict) -> str:
    abbr = team.get("abbrev", "???")
    return TEAMS.get(abbr, team.get("commonName", {}).get("default", abbr))


def slate_date(now: datetime) -> str:
    """Дата слэйта НХЛ.

    В 16:00 МСК в Северной Америке ещё утро того же дня.
    Вечерние матчи ET — это уже ночь/утро следующего дня по Москве,
    но в API они лежат на дате НХЛ «сегодня».
    После полуночи МСК берём вчерашнюю дату НХЛ, пока ночь не кончилась
    (до 12:00 МСК), чтобы ручной запуск утром не пропускал слэйт.
    """
    if now.hour < 12:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def fetch_games(date: str) -> list[dict]:
    response = requests.get(NHL_API.format(date=date), timeout=30)
    response.raise_for_status()
    payload = response.json()
    for day in payload.get("gameWeek", []):
        if day.get("date") == date:
            return day.get("games", [])
    return []


def build_message(now: datetime) -> str:
    date = slate_date(now)
    games = fetch_games(date)
    rows = []
    for game in games:
        raw = game["startTimeUTC"].replace("Z", "+00:00")
        start = datetime.fromisoformat(raw).astimezone(MSK)
        away = team_label(game["awayTeam"])
        home = team_label(game["homeTeam"])
        rows.append((start, f"{start:%H:%M}  {away} — {home}"))

    rows.sort(key=lambda item: item[0])
    night = datetime.strptime(date, "%Y-%m-%d")
    title = f"🏒 НХЛ, ночь {night.day} {MONTHS[night.month]}"

    if not rows:
        return f"{title}\n\nИгр нет."

    lines = "\n".join(text for _, text in rows)
    return f"{title}\n\n{lines}\n\nВремя московское."


def send(token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(body)


def main() -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    now = datetime.now(MSK)
    text = build_message(now)
    print(text)
    send(token, chat_id, text)


if __name__ == "__main__":
    try:
        main()
    except KeyError as exc:
        sys.exit(f"Не задана переменная {exc.args[0]}")
    except Exception as exc:
        sys.exit(f"Ошибка: {exc}")
