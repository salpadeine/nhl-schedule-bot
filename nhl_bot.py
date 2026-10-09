#!/usr/bin/env python3
"""Постит в Telegram расписание НХЛ на текущую ночь по московскому времени."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

MSK = ZoneInfo("Europe/Moscow")
NHL_API = "https://api-web.nhle.com/v1/schedule/{date}"
SCORE_API = "https://api-web.nhle.com/v1/score/{date}"
STATE_FILE = Path("last_slate.txt")

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

# custom_emoji_id из пака https://t.me/addemoji/nhl_emoji
# Пустая строка = без логотипа, пока id не вписан.
TEAM_EMOJI = {
    "ANA": "5289624869271548674",
    "BOS": "5308006629218722288",
    "BUF": "5310013096205493109",
    "CAR": "5309858584757018813",
    "CBJ": "5310168372158144305",
    "CGY": "5310229811665314792",
    "CHI": "5309943818383008756",
    "COL": "5307852654641159018",
    "DAL": "5310213533739261074",
    "DET": "5310129953675682109",
    "EDM": "5309857214662451573",
    "FLA": "5307821533308134511",
    "LAK": "5309907474369749141",
    "MIN": "5310175046537323579",
    "MTL": "5309893391171985824",
    "NJD": "5309964021909168198",
    "NSH": "5309846309740485867",
    "NYI": "5310277816514781790",
    "NYR": "5310277429967724551",
    "OTT": "5307711934332674503",
    "PHI": "5309759113314444494",
    "PIT": "5309744987167006170",
    "SEA": "5309761862093513430",
    "SJS": "5309935808269001540",
    "STL": "5309851944737578541",
    "TBL": "5474153019543136376",
    "TOR": "5310291530345356796",
    "UTA": "5292199895439023589",
    "VAN": "5309925899779447946",
    "VGK": "5310055869784794040",
    "WPG": "5310087772801868778",
    "WSH": "5310233621301304614",
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


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def logo(abbr: str) -> str:
    emoji_id = TEAM_EMOJI.get(abbr, "")
    if not emoji_id:
        return ""
    return f'<tg-emoji emoji-id="{emoji_id}">🏒</tg-emoji> '


def slate_date(now: datetime) -> str:
    """Дата слэйта НХЛ.

    В 16:00 МСК в Северной Америке ещё утро того же дня.
    Вечерние матчи ET — это уже ночь/утро следующего дня по Москве,
    но в API они лежат на дате НХЛ «сегодня».
    После полуночи МСК берём вчерашнюю дату НХЛ до 12:00,
    чтобы ручной запуск утром не пропускал слэйт.
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
        away_abbr = game["awayTeam"].get("abbrev", "")
        home_abbr = game["homeTeam"].get("abbrev", "")
        away = esc(team_label(game["awayTeam"]))
        home = esc(team_label(game["homeTeam"]))
        rows.append((start, f"{start:%H:%M}  {logo(home_abbr)}{home} — {logo(away_abbr)}{away}"))

    rows.sort(key=lambda item: item[0])
    night = datetime.strptime(date, "%Y-%m-%d")
    title = f"🏒 НХЛ, ночь {night.day} {MONTHS[night.month]}"

    if not rows:
        return f"{title}\n\nИгр нет."

    lines = "\n".join(text for _, text in rows)
    return f"{title}\n\n{lines}"


def fetch_scores(date: str) -> list[dict]:
    response = requests.get(SCORE_API.format(date=date), timeout=30)
    response.raise_for_status()
    payload = response.json()
    return [game for game in payload.get("games", []) if game.get("gameDate") == date]


def ending(game: dict) -> str:
    kind = game.get("gameOutcome", {}).get("lastPeriodType", "REG")
    if kind == "OT":
        return " ОТ"
    if kind == "SO":
        return " Б"
    return ""


def recap_link(game: dict) -> str:
    path = game.get("threeMinRecap") or ""
    if not path:
        return ""
    return f'<a href="https://www.nhl.com{esc(path)}">обзор</a>'


def build_results(now: datetime) -> str:
    date = slate_date(now)
    games = fetch_scores(date)
    rows = []
    for game in games:
        raw = game["startTimeUTC"].replace("Z", "+00:00")
        start = datetime.fromisoformat(raw).astimezone(MSK)
        away_abbr = game["awayTeam"].get("abbrev", "")
        home_abbr = game["homeTeam"].get("abbrev", "")
        away = esc(team_label(game["awayTeam"]))
        home = esc(team_label(game["homeTeam"]))
        state = game.get("gameState", "")
        if state in {"OFF", "FINAL"} and "score" in game["homeTeam"]:
            score = f"{game['homeTeam']['score']}:{game['awayTeam']['score']}{ending(game)}"
            score = f"<tg-spoiler>{esc(score)}</tg-spoiler>"
        else:
            score = "ещё идёт"
        link = recap_link(game)
        tail = f" {link}" if link else ""
        rows.append((start, f"{logo(home_abbr)}{home} — {logo(away_abbr)}{away}  {score}{tail}"))

    rows.sort(key=lambda item: item[0])
    night = datetime.strptime(date, "%Y-%m-%d")
    title = f"🏒 Итоги, ночь {night.day} {MONTHS[night.month]}"
    if not rows:
        return f"{title}\n\nИгр не было."
    return title + "\n\n" + "\n".join(text for _, text in rows)


def send(token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(body)


def post_schedule(token: str, chat_id: str, now: datetime) -> None:
    date = slate_date(now)
    if STATE_FILE.exists() and STATE_FILE.read_text().strip() == date:
        print(f"Слэйт {date} уже отправлен, повторно не пишу.")
        return
    text = build_message(now)
    print(text)
    send(token, chat_id, text)
    STATE_FILE.write_text(date + "\n")


def post_results(token: str, chat_id: str, now: datetime) -> None:
    text = build_results(now)
    print(text)
    send(token, chat_id, text)


def listen(token: str, chat_id: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{token}/setMyCommands",
        json={"commands": [
            {"command": "schedule", "description": "Расписание на ночь"},
            {"command": "results", "description": "Итоги ночи со спойлером"},
        ]},
        timeout=30,
    ).raise_for_status()
    offset = 0
    print("Слушаю /schedule и /results. Остановить: Ctrl+C.")
    while True:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"timeout": 50, "offset": offset, "allowed_updates": ["message"]},
            timeout=60,
        )
        response.raise_for_status()
        for update in response.json().get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message") or {}
            if str(message.get("chat", {}).get("id")) != str(chat_id):
                continue
            command = (message.get("text") or "").split()[0].split("@")[0]
            now = datetime.now(MSK)
            if command == "/results":
                post_results(token, chat_id, now)
            elif command == "/schedule":
                post_schedule(token, chat_id, now)


def main() -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    mode = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MODE", "schedule")).lower()
    now = datetime.now(MSK)
    if mode == "listen":
        listen(token, chat_id)
    elif mode == "results":
        post_results(token, chat_id, now)
    else:
        post_schedule(token, chat_id, now)


if __name__ == "__main__":
    try:
        main()
    except KeyError as exc:
        sys.exit(f"Не задана переменная {exc.args[0]}")
    except Exception as exc:
        sys.exit(f"Ошибка: {exc}")
