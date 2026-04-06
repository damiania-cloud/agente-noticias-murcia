import sys, logging, datetime, json, os, hashlib
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = int(os.environ.get("CHAT_ID", "0"))
SEEN_FILE = "sent_news.json"
MAX_SEEN = 500

RSS_FEEDS = [
    {"name": "LOS ALCAZARES (La Verdad)", "url": "https://www.laverdad.es/rss/2.0/?section=murcia/los-alcazares", "max": 5},
    {"name": "REGION DE MURCIA (La Verdad)", "url": "https://www.laverdad.es/rss/2.0/?section=murcia", "max": 4},
    {"name": "REGION DE MURCIA (La Opinion)", "url": "https://news.google.com/rss/search?q=site:laopiniondemurcia.es&hl=es&gl=ES&ceid=ES:es", "max": 4},
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f).get("sent", []))
    return set()


def save_seen(seen):
    seen_list = list(seen)[-MAX_SEEN:]
    with open(SEEN_FILE, "w") as f:
        json.dump({"sent": seen_list}, f)


def article_id(title):
    return hashlib.md5(title.lower().strip()[:120].encode()).hexdigest()[:16]


def fetch_rss(url, max_items):
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        articles = []
        for item in root.findall(".//item")[:max_items]:
            title = item.findtext("title", default="Sin titulo")
            link = item.findtext("link", default="").strip()
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()[:80]
                source = parts[1].strip()[:30]
            articles.append({"title": title, "source": source, "link": link})
        return articles
    except Exception as exc:
        logging.error(f"fetch error: {exc}")
        return []


def mes_es(n):
    return ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"][n-1]


def build_message(sections):
    hoy = datetime.date.today()
    lines = [f"*Noticias nuevas {hoy.day} {mes_es(hoy.month)} {hoy.year}*", ""]
    for sec in sections:
        if not sec["articles"]:
            continue
        lines.append(f"*{sec['name']}*")
        lines.append("-" * 20)
        for i, art in enumerate(sec["articles"], 1):
            src = f" [{art['source']}]" if art["source"] else ""
            if art["link"]:
                lines.append(f"{i}. {art['title']}{src} [mas]({art['link']})")
            else:
                lines.append(f"{i}. {art['title']}{src}")
        lines.append("")
    lines.append("_Bot noticias Alcazares-Murcia_")
    msg = "\n".join(lines)
    return msg[:4000]


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }).encode("utf-8")
    try:
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        if result.get("ok"):
            logging.info("Enviado OK")
            return True
        logging.error(f"Telegram error: {result}")
        return False
    except Exception as exc:
        body = ""
        if hasattr(exc, "read"):
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                pass
        logging.error(f"Excepcion: {exc} | Body: {body}")
        return False


def main():
    if not TELEGRAM_TOKEN or CHAT_ID == 0:
        print("Faltan TELEGRAM_TOKEN o CHAT_ID")
        sys.exit(1)

    seen = load_seen()
    sections = []
    new_hashes = set()

    for cfg in RSS_FEEDS:
        all_arts = fetch_rss(cfg["url"], cfg["max"])
        new_arts = []
        for art in all_arts:
            h = article_id(art["title"])
            if h not in seen:
                new_arts.append(art)
                new_hashes.add(h)
        sections.append({"name": cfg["name"], "articles": new_arts})

    total_new = sum(len(s["articles"]) for s in sections)

    if total_new == 0:
        print("Sin noticias nuevas. No se envia mensaje.")
        sys.exit(0)

    ok = send_telegram(build_message(sections))
    if ok:
        seen.update(new_hashes)
        save_seen(seen)
        print(f"Enviado OK: {total_new} noticias nuevas.")
    else:
        print("Error al enviar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
