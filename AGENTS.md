# AGENTS.md

Istruzioni per gli agenti che lavorano in questo repository.

## Cosa fa il progetto

Singolo script Python (`monitor.py`) che scrapa la pagina delle sessioni OFA
Test Polimi di Linguaviva, confronta il risultato con lo snapshot precedente in
`last_sessions.json` e invia una notifica Telegram solo in caso di variazioni.
Eseguito da `.github/workflows/monitor.yml`.

## Comandi

```bash
# dipendenze
pip install -r requirements.txt

# esecuzione (richiede TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID)
python monitor.py

# verifica sintattica
python -m py_compile monitor.py
```

Non esiste una suite di test. Prima di modificare `fetch_sessions`, verifica il
parsing su una pagina reale (in locale, senza token Telegram lo script funziona
e salva comunque lo stato) oppure su un fixture HTML.

## Struttura

```
monitor.py                      script unico: fetch, diff, notifica
requirements.txt                requests, beautifulsoup4
last_sessions.json              snapshot corrente, committato dalla workflow
last_sessions_old.json          snapshot storico, non usato
.github/workflows/monitor.yml   workflow: workflow_dispatch + repository_dispatch
```

## Vincoli importanti

- **Lo scraping è fragile per definizione.** `fetch_sessions` dipende dal markup
  di linguaviva.net tramite selettori CSS (`items-center`, `gap-5`, `uppercase`,
  `leading-none`, `font-serif`, `font-semibold`) e da regex in italiano su
  "posti disponibili", "Iscrizioni chiuse", "Esaurito". Se cambi i selettori,
  verifica che `raw_text` continenga ancora i token usati dal resto della logica.
- **Il campo `key` è l'identità di una sessione** (`"17 SET - OFA Test Polimi"`).
  Cambiarne il formato invalida l'intero storico in `last_sessions.json` e fa
  scattare notifiche "SESSIONE RIMOSSA" + "NUOVA DATA" per tutte le sessioni.
  Se serve una migrazione, prevedi un fallback di matching su giorno/mese.
- **`last_sessions.json` è lo stato, non un output.** Non eliminarlo per
  "pulizia": al primo avvio senza stato viene reinviato il messaggio di
  benvenuto e si perde la capacità di distinguere cambi reali da rumore.
- **Errori di rete non devono toccare lo stato.** `fetch_sessions` solleva,
  `main` esce con codice 1 prima di `save_current_state`. Mantieni questa
  proprietà: uno stato corrotto da una pagina irraggiungibile produce falsi
  allarmi.
- **Il formato del messaggio usa Markdown Telegram.** Testo non escapato nei
  titoli con `_` o `*` rompe la formattazione di output.
- **Niente segreti nel repository.** Token e Chat ID arrivano solo da variabili
  d'ambiente / GitHub Secrets. Lo script deve continuare a funzionare con
  warning se mancano, non sollevare.
- **Non aggiungere trigger `schedule:`** alla workflow se non richiesto: la
  pianificazione è delegata a un cron esterno via `repository_dispatch`. I
  runner gratuiti sono limitati e il sito è esterno.

## Stile

- Commenti e stringhe utente in italiano, coerente con il resto del codice.
- Log con prefisso `[INFO]`, `[WARN]`, `[ERROR]`.
- Nessuna dipendenza aggiuntiva senza motivo chiaro: il progetto è volutamente
  minimale (`requests` + `beautifulsoup4`).
- Nessun commento di codice esplicativo se non strettamente necessario.

## Workflow e git

La workflow committa automaticamente `last_sessions.json` con il messaggio
`update: aggiornato stato sessioni Linguaviva [skip ci]`. Non modificare quel
file a mano per "aggiornarlo": verrebbe sovrascritto alla prossima esecuzione e
genererebbe notifiche Telegram indesiderate.

Branch principale: `main`. Le commit automatiche arrivano da
`github-actions[bot]`: se ricavi da un merge/rebase, verifica di non sovrascrivere
il commit di stato più recente.