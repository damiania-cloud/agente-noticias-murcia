import sys, logging, datetime, json, os
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = int(os.environ.get("CHAT_ID", "0"))

RSS_FEEDS = [
    {"name": "Los Alcazares", "url": "https://news.google.com/rss/search?q=%22Los+Alc%C3%A1zares%22&hl=es&gl=ES&ceid=ES:es", "max": 5},
    {"name": "Region de Murcia", "url": "https://news.google.com/rss/search?q=%22Regi%C3%B3n+de+Murcia%22&hl=es&gl=ES&ceid=ES:es", "max": 7},
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}

def fetch_rss(url, max_items):
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        items = root.findall(".//item")[:max_items]
        articles = []
        for item in items:
            title = item.findtext("title", default="Sin titulo")
            link = item.findtext("link", default="")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip()
            if len(title) > 90:
                title = title[:87] + "..."
            articles.append({"title": title, "link": link, "source": source})
        return articles
    except Exception as exc:
        logging.error(f"Error en {url}: {exc}")
    return []

def mes_es(n):
    return ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"][n-1]

def build_message(sections):
    hoy = datetime.date.today()
    lines = [f"Noticias del dia - {hoy.day} de {mes_es(hoy.month)} de {hoy.year}", ""]
    for sec in sections:
        lines.append(sec["name"].upper())
        lines.append("-" * 20)
        if not sec["articles"]:
            lines.append("Sin noticias hoy.")
        else:
            for i, art in enumerate(sec["articles"], 1):
                src = f" ({art['source']})" if art["source"] else ""
                lines.append(f"{i}. {art['title']}{src}")
                lines.append(f"   {art['link']}")
        lines.append("")
    lines.append("Agente automatico - Los Alcazares & Murcia")
    return "\n".join(lines)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}).encode("utf-8")
    try:
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        if result.get("ok"):
            logging.info("Mensaje enviado.")
            return True
        logging.error(f"Error Telegram: {result}")
        return False
    except Exception as exc:
        logging.error(f"Excepcion: {exc}")
        return False

def main():
    if not TELEGRAM_TOKEN or CHAT_ID == 0:
        print("Faltan TELEGRAM_TOKEN o CHAT_ID")
        sys.exit(1)
    sections = []
    for cfg in RSS_FEEDS:
        arts = fetch_rss(cfg["url"], cfg["max"])
        sections.append({"name": cfg["name"], "articles": arts})
    ok = send_telegram(build_message(sections))
    if ok:
        print("Noticias enviadas correctamente.")
    else:
        print("Error al enviar.")
        sys.exit(1)

if __name__ == "__main__":
    main()
