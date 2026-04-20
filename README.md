# 📊 Markt Analyse

Streamlit-App für tägliche technische Analysen von Aktien, Krypto und Edelmetallen — mit KI-Unterstützung und optionalem E-Mail-Versand.

**Live:** [share.streamlit.io](https://share.streamlit.io) · Repo: `anakinsky33/markt-analyse` · Branch: `main`

---

## Funktionsumfang

### Assets
- **Aktien** — S&P 500 fest + beliebige Ticker (kommagetrennt, z.B. `NVDA, SAP.DE`)
- **Krypto** — Bitcoin & XRP (Daten via Kraken API)
- **Edelmetalle** — Gold & Silber (Daten via Yahoo Finance)
- **Ticker-Suche** — Firmenname eingeben → Ticker per Finnhub-Suche finden

### Technische Analyse
- Elliott-Wellen-Analyse
- EMA 50 / EMA 200 (Golden Cross / Death Cross)
- RSI (14) mit Überkauft/Überverkauft-Erkennung
- MACD mit Histogramm-Momentum
- Regelbasierte Prognose: Bull/Bear %, Hauptszenario, Alternativszenario, Invalidierungslevel

### KI-Analyse (wählbar)
| Modus | Modell | Hinweis |
|-------|--------|---------|
| Regelbasiert | — | Kein API-Key nötig |
| Claude (Anthropic) | claude-haiku-4-5 | `sk-ant-...` Key |
| Gemini (Google) | gemini-2.0-flash | `AIza...` Key, Free Tier |

Die KI beginnt **immer mit der 48h-Prognose + Handlungsempfehlung**, gefolgt von der detaillierten Analyse (Elliott, EMA, RSI, MACD, Fundamentals, Gesamtbild).

### Darstellung
- Gestylte Karte pro Asset: dunkler Header, Prognose-Banner, Kursziel-Boxen, Indikatortabelle
- 48h-Prognose prominent hervorgehoben (vor der Detailanalyse)
- Fundamentaldaten bei Aktien (via Finnhub)

### E-Mail
- Optionaler Versand nach der Analyse
- Gleiches HTML-Format wie App-Darstellung
- Gmail via App-Passwort (SMTP Port 465 / Fallback 587)

---

## Einrichtung auf Streamlit Cloud

1. Fork oder nutze `anakinsky33/markt-analyse` direkt
2. Streamlit Cloud → **New app** → Repo: `markt-analyse`, Branch: `main`, File: `app.py`
3. **Secrets** unter App-Einstellungen eintragen:

```toml
ANTHROPIC_API_KEY  = "sk-ant-..."
GOOGLE_AI_KEY      = "AIza..."
FINNHUB_API_KEY    = "..."
GMAIL_ABSENDER     = "deine@gmail.com"
GMAIL_APP_PASSWORT = "xxxx xxxx xxxx xxxx"
EMPFAENGER         = "empfaenger@mail.com"
```

> Secrets sind optional — alle Keys können auch direkt in der Sidebar eingegeben werden.

---

## Datenquellen

| Quelle | Verwendung | Kosten |
|--------|-----------|--------|
| Yahoo Finance v8 | Aktien & Edelmetall OHLC | kostenlos |
| Kraken Public API | BTC & XRP OHLC (Daily) | kostenlos |
| Finnhub | Fundamentaldaten, Ticker-Suche | kostenlos (Free Tier) |

---

## Versionshistorie

| Version | Änderung |
|---------|----------|
| 1.8.0 | Schlüsselwörter farbig, Erklärungstext schwarz; iframe-Höhe 5000 |
| 1.7.0 | 48h-Prognose zuerst im Prompt; vollständiger Markdown-Konverter; max_tokens 4000 |
| 1.6.0 | 48h-Prognose vor Detailanalyse; `##`/`**` durch HTML ersetzt |
| 1.5.0 | Gemini 429 Rate-Limit Meldung |
| 1.4.0 | Versionsnummer im App-Header |
| 1.3.0 | render_card() = bewährtes E-Mail-Format; Gemini → gemini-2.0-flash |
| 1.0.0 | Initiale Version: Aktien + Krypto + Edelmetalle vereint |

---

*Keine Anlageberatung — automatisch generierte technische Analyse.*
