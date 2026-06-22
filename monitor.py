import os
import re
import json
import time
import hashlib
from pathlib import Path
from urllib.parse import quote_plus

import requests
import feedparser
from bs4 import BeautifulSoup


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ARTISTS_FILE = Path("artists.txt")
SEEN_FILE = Path("seen.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CelebrityNewsEventBot/1.0)"
}

EVENT_KEYWORDS = [
    "attends",
    "arrives",
    "arrival",
    "premiere",
    "screening",
    "red carpet",
    "film festival",
    "festival",
    "gala",
    "awards",
    "award",
    "fashion week",
    "front row",
    "after party",
    "after-party",
    "dinner",
    "launch",
    "presentation",
    "photocall",
    "press conference",
    "portrait session",
]

SIGHTING_KEYWORDS = [
    "celebrity sightings",
    "celebrity sighting",
    "sightings in",
    "seen at",
    "seen arriving",
    "seen leaving",
    "seen outside",
    "spotted",
    "out and about",
    "leaves",
    "outside",
    "arriving at",
    "departing",
    "airport",
    "hotel",
    "restaurant",
    "studio",
]

PROJECT_KEYWORDS = [
    "joins cast",
    "join cast",
    "cast in",
    "to star",
    "set to star",
    "will star",
    "starring",
    "new movie",
    "new film",
    "new series",
    "new show",
    "upcoming film",
    "upcoming movie",
    "upcoming series",
    "upcoming project",
    "announced",
    "in development",
    "greenlit",
    "renewed",
    "cancelled",
    "trailer",
    "teaser",
    "first look",
    "poster",
    "release date",
    "premieres on",
    "production begins",
    "begins filming",
    "starts filming",
    "filming",
    "wraps filming",
    "wrapped filming",
    "on set",
    "behind the scenes",
    "interview",
    "cover story",
    "magazine cover",
]

IGNORE_KEYWORDS = [
    "birthday",
    "biography",
    "wiki",
    "net worth",
    "height",
    "age",
    "instagram",
    "tiktok",
    "fan account",
    "best movies",
    "ranking",
    "where to watch",
    "quiz",
    "horoscope",
]


def load_artists():
    artists = []
    for line in ARTISTS_FILE.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            artists.append(name)
    return artists


def load_seen():
    if not SEEN_FILE.exists():
        return {}
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def item_id(source, artist, title, link):
    raw = f"{source}|{artist}|{title}|{link}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def classify_alert(title):
    text = title.lower()

    if any(bad in text for bad in IGNORE_KEYWORDS):
        return None

    if any(word in text for word in EVENT_KEYWORDS):
        return "EVENTO/APARIÇÃO"

    if any(word in text for word in SIGHTING_KEYWORDS):
        return "SIGHTING/CANDID"

    if any(word in text for word in PROJECT_KEYWORDS):
        return "NOVO PROJETO/NOTÍCIA"

    return None


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Faltam TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID nos Secrets.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    if not r.ok:
        print("Erro Telegram:", r.status_code, r.text)


def get_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code >= 400:
            print(f"Status {r.status_code}: {url}")
            return None
        return r.text
    except Exception as exc:
        print(f"Erro ao acessar {url}: {exc}")
        return None


def extract_from_public_page(html, source, artist, source_url):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    if soup.title:
        candidates.append((clean_text(soup.title.get_text(" ")), source_url))

    for a in soup.find_all("a", href=True):
        label = clean_text(a.get("title", "")) or clean_text(a.get("aria-label", "")) or clean_text(a.get_text(" "))
        href = a["href"]

        if not label:
            continue

        if artist.lower() not in label.lower():
            continue

        if href.startswith("/"):
            if source == "Getty Images":
                link = "https://www.gettyimages.com" + href
            elif source == "WireImage":
                link = "https://www.wireimage.com" + href
            elif source == "Shutterstock Editorial":
                link = "https://www.shutterstock.com" + href
            else:
                link = source_url
        elif href.startswith("http"):
            link = href
        else:
            link = source_url

        category = classify_alert(label)
        if category:
            candidates.append((label, link, category))

    unique = {}
    for item in candidates:
        if len(item) == 2:
            title, link = item
            category = classify_alert(title)
        else:
            title, link, category = item

        if not category:
            continue

        unique[(title, link)] = {
            "source": source,
            "artist": artist,
            "title": title,
            "link": link,
            "category": category,
        }

    return list(unique.values())[:8]


def check_google_news(artist):
    query = quote_plus(
        f'"{artist}" ('
        f'"attends" OR "premiere" OR "red carpet" OR "screening" OR "film festival" OR '
        f'"celebrity sightings" OR "spotted" OR "seen arriving" OR "seen leaving" OR '
        f'"joins cast" OR "set to star" OR "new film" OR "new series" OR "trailer" OR '
        f'"first look" OR "release date" OR "begins filming" OR "on set" OR "cover story"'
        f')'
    )
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    feed = feedparser.parse(url)
    results = []

    for entry in feed.entries[:20]:
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")

        if not title or not link:
            continue

        if artist.lower() not in title.lower():
            continue

        category = classify_alert(title)
        if not category:
            continue

        results.append({
            "source": "Google News",
            "artist": artist,
            "title": title,
            "link": link,
            "category": category,
        })

    return results[:8]


def check_getty(artist):
    slug = artist.lower().replace(" ", "-")
    url = f"https://www.gettyimages.com/photos/{slug}?sort=newest"
    html = get_page(url)
    if not html:
        return []
    return extract_from_public_page(html, "Getty Images", artist, url)


def check_wireimage(artist):
    query = quote_plus(artist)
    url = f"https://www.wireimage.com/search?phrase={query}&sort=newest"
    html = get_page(url)
    if not html:
        return []
    return extract_from_public_page(html, "WireImage", artist, url)


def check_shutterstock(artist):
    query = quote_plus(artist)
    url = f"https://www.shutterstock.com/editorial/search/{query}?sort=newest"
    html = get_page(url)
    if not html:
        return []
    return extract_from_public_page(html, "Shutterstock Editorial", artist, url)


def format_alert(item):
    emoji = {
        "EVENTO/APARIÇÃO": "🚨",
        "SIGHTING/CANDID": "📸",
        "NOVO PROJETO/NOTÍCIA": "🎬",
    }.get(item["category"], "🔔")

    return (
        f"{emoji} {item['category']}\n\n"
        f"Artista: {item['artist']}\n"
        f"Fonte: {item['source']}\n\n"
        f"{item['title']}\n\n"
        f"{item['link']}"
    )


def main():
    artists = load_artists()
    seen = load_seen()
    total_sent = 0

    for artist in artists:
        print(f"Verificando: {artist}")

        items = []
        items.extend(check_google_news(artist))
        time.sleep(2)

        items.extend(check_getty(artist))
        time.sleep(2)

        items.extend(check_wireimage(artist))
        time.sleep(2)

        items.extend(check_shutterstock(artist))
        time.sleep(2)

        for item in items:
            uid = item_id(item["source"], item["artist"], item["title"], item["link"])
            if uid in seen:
                continue

            seen[uid] = {
                "source": item["source"],
                "artist": item["artist"],
                "title": item["title"],
                "link": item["link"],
                "category": item["category"],
                "first_seen": int(time.time()),
            }

            send_telegram(format_alert(item))
            total_sent += 1
            time.sleep(1)

    save_seen(seen)
    print(f"Concluído. Alertas enviados: {total_sent}")


if __name__ == "__main__":
    main()
