import os
import sys
import json
import requests
from bs4 import BeautifulSoup

# Riconfigura l'output di sistema in UTF-8 per supportare emoji ed elenchi speciali su Windows/Linux
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
    """Invia un messaggio Telegram tramite la Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Token Telegram o Chat ID non impostati. Messaggio non inviato:")
        print(message)
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
    """Scarica la pagina ed estrae tutte le sessioni di esame presenti."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache"
    }

    response = requests.get(URL, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    sessions = []

    # Cerchiamo tutti i blocchi d'esame
    # Ciascuna riga ha la classe 'flex items-center gap-5' o contiene elementi d'esame
    # Usiamo una ricerca flessibile per catturare la struttura
    blocks = soup.find_all("div", class_=lambda c: c and "items-center" in c and "gap-5" in c)

    for block in blocks:
        text_block = block.get_text(separator=" ", strip=True)
        # Verifichiamo che sia un blocco relativo a un appello d'esame
        if "OFA Test Polimi" in text_block or any(m in text_block for m in ["GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"]):
            # Estrazione Mese e Giorno
            month_elem = block.find("span", class_=lambda c: c and "uppercase" in c)
            day_elem = block.find("span", class_=lambda c: c and "leading-none" in c)
            title_elem = block.find(["h3", "h4", "div"], class_=lambda c: c and ("font-serif" in c or "font-semibold" in c))

            month = month_elem.get_text(strip=True) if month_elem else ""
            day = day_elem.get_text(strip=True) if day_elem else ""
            title = title_elem.get_text(strip=True) if title_elem else "Esame"

            # Estrazione orari/dettagli dal testo
            full_text = block.get_text(separator=" | ", strip=True)

            # Verifica stato (Aperto vs Chiuso)
            is_open = True
            if "Iscrizioni chiuse" in full_text or "Esaurito" in full_text:
                is_open = False
                status_str = "🔴 Iscrizioni chiuse"
            else:
                status_str = "🟢 ISCRIZIONI APERTE / POSTI DISPONIBILI"

            # Costruiamo una chiave unica per identificare la sessione
            session_key = f"{day} {month} - {title}"
            
            sessions.append({
                "key": session_key,
                "day": day,
                "month": month,
                "title": title,
                "is_open": is_open,
                "status_str": status_str,
                "raw_text": full_text
            })

    return sessions


def load_previous_state():
    """Carica lo stato precedente dal file JSON."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Errore nella lettura di {STATE_FILE}: {e}")
    return None


def save_current_state(state):
    """Salva lo stato corrente nel file JSON."""
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
    for s in current_sessions:
        print(f"  - [{s['status_str']}] {s['key']} ({s['raw_text']})")

    prev_state = load_previous_state()
    
    # Se è la primissima esecuzione (non esiste ancora last_sessions.json)
    if prev_state is None:
        print("[INFO] Prima esecuzione rilevata. Inizializzazione file di stato...")
        save_current_state(current_sessions)
        
        # Inviamo un messaggio di benvenuto/conferma
        welcome_msg = (
            "🤖 *Bot Monitoraggio Linguaviva Attivato!*\n\n"
            f"Trovate inizialmente *{len(current_sessions)} sessioni* per OFA Test Polimi.\n"
            "Riceverai una notifica non appena sarà pubblicata una nuova data o si apriranno le iscrizioni!\n\n"
            f"🔗 [Apri Sito Linguaviva]({URL})"
        )
        send_telegram_message(welcome_msg)
        return

    # Mappiamo le vecchie sessioni per chiave
    prev_map = {s["key"]: s for s in prev_state}
    curr_map = {s["key"]: s for s in current_sessions}

    notifications = []

    # 1. Controllo nuove sessioni o riaperture
    for key, curr in curr_map.items():
        if key not in prev_map:
            # NUOVA SESSIONE TROVATA!
            status_icon = "🚨 *NUOVA DATA DISPONIBILE!*" if curr["is_open"] else "ℹ️ *Nuova data inserita (ancora chiusa)*"
            notifications.append(
                f"{status_icon}\n"
                f"📅 *Data:* {curr['key']}\n"
                f"📌 *Stato:* {curr['status_str']}\n"
                f"📝 *Dettagli:* {curr['raw_text']}"
            )
        else:
            prev = prev_map[key]
            # Se la sessione era chiusa ed ora è aperta!
            if not prev["is_open"] and curr["is_open"]:
                notifications.append(
                    f"🎉 *ISCRIZIONI APERTE!*\n"
                    f"📅 *Data:* {curr['key']}\n"
                    f"📌 *Stato:* {curr['status_str']}\n"
                    f"📝 *Dettagli:* {curr['raw_text']}"
                )

    # Se ci sono modifiche rilevanti, inviamo le notifiche
    if notifications:
        print(f"[INFO] Trovate {len(notifications)} novità! Invio notifiche...")
        for notif in notifications:
            full_msg = f"{notif}\n\n👉 [PRENOTA SUBITO SU LINGUAVIVA]({URL})"
            send_telegram_message(full_msg)
    else:
        print("[INFO] Nessun cambiamento rilevato rispetto all'ultimo controllo.")

    # Aggiorniamo sempre lo stato corrente
    save_current_state(current_sessions)


if __name__ == "__main__":
    main()
