import os, json, time, hashlib
import urllib.request
import xml.etree.ElementTree as ET

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen": []}

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
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def parse_rss(xml_bytes):
    # Works for RSS 2.0 + basic Atom
    out = []
    root = ET.fromstring(xml_bytes)

    # RSS items
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            out.append((title, link, pub))

    # Atom entries
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_el.get("href") if link_el is not None else "").strip()
        pub = (entry.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
        if title and link:
            out.append((title, link, pub))

    return out

def key(title, link):
    h = hashlib.sha256((title + "|" + link).encode("utf-8")).hexdigest()
    return h

def main():
    state = load_state()
    seen = set(state.get("seen", []))

    with open("feeds.txt", "r", encoding="utf-8") as f:
        feeds = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    new_keys = []
    for feed in feeds:
        try:
            xml_bytes = fetch(feed)
            items = parse_rss(xml_bytes)
            # newest first to oldest last -> send oldest first
            items = list(reversed(items))[-10:]  # limit bursts
            for title, link, pub in items:
                k = key(title, link)
                if k in seen:
                    continue
                msg = f"📌 {title}\n🔗 {link}"
                tg_send(msg)
                new_keys.append(k)
                time.sleep(1)
        except Exception as e:
            # optional: send error to channel (commented to avoid spam)
            # tg_send(f"⚠️ Feed error: {feed}\n{e}")
            pass

    # keep last 500 seen
    merged = list(seen) + new_keys
    merged = merged[-500:]
    save_state({"seen": merged})

if __name__ == "__main__":
    main()
