# Linguaviva OFA Monitor

Bot di monitoraggio che controlla periodicamente la pagina delle sessioni di
[Linguaviva](https://www.linguaviva.net/it/sessioni?exam=ofa-test-polimi) per
l'esame **OFA Test Polimi** e invia una notifica Telegram quando qualcosa cambia.

Obiettivo pratico: accorgersi in pochi secondi che si è aperta una nuova data di
esame, o che sono comparsi posti disponibili, per prenotare prima che finiscano.

## Come funziona

Il repository contiene un singolo script Python (`monitor.py`) eseguito da una
GitHub Actions workflow (`.github/workflows/monitor.yml`). A ogni esecuzione:

1. **Scarica** la pagina delle sessioni con `requests`, usando un `User-Agent`
   da browser per non essere bloccato.
2. **Estrae** le sessioni con `BeautifulSoup`, cercando i blocchi `div` con le
   classi `items-center gap-5`. Per ogni blocco ricava:
   - giorno e mese (es. `17`, `SET`);
   - titolo della sessione;
   - stato (`Iscrizioni chiuse` / `Esaurito` → 🔴, altrimenti 🟢);
   - numero di posti disponibili, tramite regex su `N posti disponibili`;
   - dettagli opzionali (`Home Edition`, orario `15:30`).
3. **Confronta** il risultato con `last_sessions.json`, lo snapshot salvato
   dell'esecuzione precedente.
4. **Notifica** su Telegram solo se ci sono differenze.
5. **Salva** il nuovo snapshot in `last_sessions.json`.

Lo stato viene versionato su Git, così ogni esecuzione parte da una base
condivisa e il backup del monitoraggio è implicito nella cronologia dei commit.

## Modifiche rilevate

| Caso | Messaggio |
| --- | --- |
| Nuova data con iscrizioni aperte | 🚨 NUOVA DATA DISPONIBILE |
| Nuova data con iscrizioni chiuse | ℹ️ Nuova data inserita (chiusa) |
| Iscrizioni chiuse → aperte | 🎉 ISCRIZIONI APERTE |
| Iscrizioni aperte → chiuse | 🔒 ISCRIZIONI CHIUSE |
| Posti disponibili cambiati | 📊 VARIAZIONE POSTI (prima ➡️ dopo) |
| Sessione sparita dal sito | 🗑️ SESSIONE RIMOSSA DAL SITO |

Ogni notifica include anche il riepilogo completo delle sessioni correnti e il
link alla pagina di prenotazione.

Al **primo avvio** (assenza di `last_sessions.json`) viene inviato un messaggio
di benvenuto con il riepilogo, senza notifiche di cambiamento.

## Configurazione

Il bot Telegram si configura tramite due variabili d'ambiente:

| Variabile | Descrizione |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token fornito da [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | ID della chat (personale o gruppo) destinataria |

In **GitHub**: *Settings → Secrets and variables → Actions → New repository secret*.

Se le variabili non sono impostate lo script **non fallisce**: stampa un
avviso e continua con il salvataggio dello stato.

### Ottenere il Chat ID

Invia un messaggio al bot, poi:

```bash
curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
```

Il campo `result[].message.chat.id` è il valore da usare.

## Esecuzione in locale

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt

$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_CHAT_ID="987654321"

python monitor.py
```

Dipendenze: `requests` e `beautifulsoup4` (vedi `requirements.txt`).

Lo script forza la codifica UTF-8 di stdout/stderr, quindi i messaggi con
accents ed emoji si vedono correttamente anche sulla console di Windows.

## Automazione

La workflow è attivata da:

- `workflow_dispatch` — esecuzione manuale dalla scheda **Actions** del repo;
- `repository_dispatch` — evento esterno, utile per pianificare i controlli con
  un cron esterno (cron-job.com, Upstash, un cron su una VPS, …).

La schedulazione interna a GitHub Actions (`schedule:`) è stata rimossa di
intenzione: i runner gratuiti sono limitati e il workflow effettua richieste
verso un sito esterno.

### Pianificazione con cron-job.org

1. Crea un account su cron-job.org e genera un token.
2. In **Settings → Secrets** aggiungi `GH_TOKEN` (Personal Access Token GitHub
   con scope `repo` o fine-grained con permessi *Actions: write* e *Contents:
   read/write* sulla repo).
3. Crea un job con esecuzione ogni N minuti e questa richiesta:

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/mttrossi-cmyk/linguaviva-monitor/dispatches \
  -d '{"event_type":"monitor-sessions"}'
```

4. Il commit automatico di `last_sessions.json` viene eseguito dalla workflow
   stessa con `github-actions[bot]`.

Frequenze tipiche: ogni 5 minuti per massima reattività, ogni 15-30 minuti per
essere meno invasivi. Il sito non va interrogato più volte del necessario.

## Struttura del repository

```
monitor.py                      script di scraping, diff e notifica
requirements.txt                dipendenze Python
last_sessions.json              snapshot corrente (aggiornato dalla workflow)
last_sessions_old.json          snapshot storico, non più usato
.github/workflows/monitor.yml   workflow GitHub Actions
```

## Note operative

- Lo scraping dipende dal markup della pagina: se Linguaviva cambia il layout,
  `fetch_sessions` può restituire zero sessioni e il bot lo segnalerà con
  *"Nessuna sessione trovata"* nei messaggi. È un segnale utile per accorgersi
  subito di un breakage.
- Il file di stato viene riscritto a ogni esecuzione. Per **resettare** il
  monitoraggio e ricevere di nuovo il messaggio di benvenuto basta cancellare
  `last_sessions.json` (locale e/o sul repo) e rieseguire.
- Se la pagina risponde con errore HTTP, lo script esce con codice `1` senza
  toccare lo stato salvato, così l'esecuzione successiva riparte sanamente.
- Il formato del messaggio usa Markdown di Telegram: testo con `_` o `*` nei
  titoli delle sessioni romperebbe la formattazione.

## Note legali

Progetto personale a scopo informativo. Non affiliato a Linguaviva. Rispetta
i termini di servizio del sito e i limiti di frequenza delle richieste.