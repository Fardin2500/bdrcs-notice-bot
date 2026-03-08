import os
import json
import time
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen": [], "seen_titles": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

def tg_send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": "false"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def clean_link(link):
    parsed = urllib.parse.urlparse(link)
    return urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        "",
        ""
    ))

def parse_rss(xml_bytes):
    out = []
    root = ET.fromstring(xml_bytes)

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            out.append((title, clean_link(link), pub))

    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_el.get("href") if link_el is not None else "").strip()
        pub = (entry.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
        if title and link:
            out.append((title, clean_link(link), pub))

    return out

def make_key(title, link):
    text = f"{title.lower()}|{link.lower()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def normalize_title(title):
    return " ".join(title.lower().split())

def main():
    state = load_state()
    seen = set(state.get("seen", []))
    seen_titles = set(state.get("seen_titles", []))

    with open("feeds.txt", "r", encoding="utf-8") as f:
        feeds = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    new_seen = []
    new_titles = []

    for feed in feeds:
        try:
            xml_bytes = fetch(feed)
            items = parse_rss(xml_bytes)

            # পুরনো থেকে নতুন পাঠাবে
            items = list(reversed(items))[-10:]

            for title, link, pub in items:
                title_norm = normalize_title(title)
                item_key = make_key(title, link)

                if item_key in seen:
                    continue

                if title_norm in seen_titles:
                    continue

                msg = f"📌 {title}\n🔗 {link}"
                tg_send(msg)

                new_seen.append(item_key)
                new_titles.append(title_norm)
                time.sleep(1)

        except Exception:
            pass

    all_seen = list(seen) + new_seen
    all_titles = list(seen_titles) + new_titles

    state = {
        "seen": all_seen[-1000:],
        "seen_titles": all_titles[-1000:]
    }
    save_state(state)

if __name__ == "__main__":
    main()
