import os
import sys
import json
import requests
from bs4 import BeautifulSoup

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

URL = "https://www.linguaviva.net/it/sessioni?exam=ofa-test-polimi"
STATE_FILE = "last_sessions.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Token Telegram o Chat ID non impostati.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print("[INFO] Notifica Telegram inviata con successo!")
        return True
    except Exception as e:
        print(f"[ERROR] Errore nell'invio del messaggio Telegram: {e}")
        return False


def fetch_sessions():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache"
    }

    response = requests.get(URL, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    sessions = []

    blocks = soup.find_all("div", class_=lambda c: c and "items-center" in c and "gap-5" in c)

    for block in blocks:
        text_block = block.get_text(separator=" ", strip=True)
        if "OFA Test Polimi" in text_block or any(m in text_block for m in ["GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"]):
            month_elem = block.find("span", class_=lambda c: c and "uppercase" in c)
            day_elem = block.find("span", class_=lambda c: c and "leading-none" in c)
            title_elem = block.find(["h3", "h4", "div"], class_=lambda c: c and ("font-serif" in c or "font-semibold" in c))

            month = month_elem.get_text(strip=True) if month_elem else ""
            day = day_elem.get_text(strip=True) if day_elem else ""
            title = title_elem.get_text(strip=True) if title_elem else "OFA Test Polimi"

            full_text = block.get_text(separator=" | ", strip=True)

            if "Iscrizioni chiuse" in full_text or "Esaurito" in full_text:
                is_open = False
                status_icon = "🔴"
                status_label = "Iscrizioni chiuse"
            else:
                is_open = True
                status_icon = "🟢"
                status_label = "POSTI DISPONIBILI / PRENOTABILE!"

            details = []
            if "Home Edition" in full_text:
                details.append("🏠 Home Edition")
            if "15:30" in full_text:
                details.append("🕒 Ore 15:30")

            details_str = " - " + " ".join(details) if details else ""
            session_key = f"{day} {month} - {title}"
            
            sessions.append({
                "key": session_key,
                "day": day,
                "month": month,
                "title": title,
                "is_open": is_open,
                "status_icon": status_icon,
                "status_label": status_label,
                "details_str": details_str,
                "raw_text": full_text
            })

    return sessions


def build_telegram_summary(sessions_list, header_title=""):
    lines = []
    if header_title:
        lines.append(header_title)
        lines.append("")

    lines.append("📋 *RIEPILOGO SESSIONI OFA TEST POLIMI:*")
    lines.append(" ")
    lines.append("──────────────────────────")

    if not sessions_list:
        lines.append("⚠️ _Nessuna sessione trovata al momento sul sito._")
    else:
        for s in sessions_list:
            lines.append(f"{s['status_icon']} *{s['day']} {s['month']}* | {s['status_label']}{s['details_str']}")

    lines.append("──────────────────────────")
    lines.append(" ")
    lines.append(f"🔗 [Prenota SUBITO su Linguaviva]({URL})")
    
    return "\n".join(lines)


def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Errore nella lettura di {STATE_FILE}: {e}")
    return None


def save_current_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    print("[INFO] Avvio controllo sessioni Linguaviva...")
    
    try:
        current_sessions = fetch_sessions()
    except Exception as e:
        print(f"[ERROR] Impossibile scaricare le sessioni: {e}")
        sys.exit(1)

    print(f"[INFO] Trovate {len(current_sessions)} sessioni nella pagina.")
    prev_state = load_previous_state()
    
    if prev_state is None:
        print("[INFO] Prima esecuzione o file di stato assente. Inizializzazione...")
        save_current_state(current_sessions)
        welcome_header = "🤖 *Bot Monitoraggio Linguaviva Attivo!*"
        msg = build_telegram_summary(current_sessions, welcome_header)
        send_telegram_message(msg)
        return

    prev_map = {s["key"]: s for s in prev_state}
    curr_map = {s["key"]: s for s in current_sessions}

    has_changes = False
    change_reasons = []

    for key, curr in curr_map.items():
        if key not in prev_map:
            has_changes = True
            if curr["is_open"]:
                change_reasons.append(f"🚨 *NUOVA DATA DISPONIBILE:* {curr['key']}")
            else:
                change_reasons.append(f"ℹ️ *Nuova data inserita:* {curr['key']}")
        else:
            prev = prev_map[key]
            if not prev.get("is_open", False) and curr["is_open"]:
                has_changes = True
                change_reasons.append(f"🎉 *ISCRIZIONI APERTE:* {curr['key']}")

    if has_changes:
        print(f"[INFO] Trovati cambiamenti! Inviando la notifica...")
        header = "📢 *AGGIORNAMENTO LINGUAVIVA!*\n" + "\n".join(change_reasons)
        full_msg = build_telegram_summary(current_sessions, header)
        send_telegram_message(full_msg)
    else:
        print("[INFO] Nessun cambiamento rilevato rispetto all'ultimo controllo.")

    save_current_state(current_sessions)


if __name__ == "__main__":
    main()
