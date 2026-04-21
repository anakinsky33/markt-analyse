# 📊 Markt Analyse

Streamlit-App für tägliche technische Analysen von Aktien, Krypto und Edelmetallen — mit KI-Unterstützung und optionalem E-Mail-Versand.

**Live:** [share.streamlit.io](https://share.streamlit.io) · Repo: `anakinsky33/markt-analyse` · Branch: `main`

---

## Funktionsumfang

### Assets
- **Aktien** — S&P 500 fest + beliebige Ticker (kommagetrennt, z.B. `NVDA, SAP.DE`)
- **Krypto** — Bitcoin & XRP (Daten via Kraken API) + beliebige Coins (kommagetrennt, z.B. `ETH, SOL, DOGE`) via Kraken, Fallback Yahoo Finance
- **Edelmetalle** — Gold & Silber (Daten via Yahoo Finance)
- **Ticker-Suche** — Firmenname eingeben → Ticker per Finnhub-Suche finden
- **Alle Assets standardmäßig abgewählt** — nur gewünschte Assets ankreuzen

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
| Claude (Anthropic) | claude-haiku-4-5 | `sk-ant-...` Key, max 4000 Token |
| Gemini (Google) | auto-erkannt (bevorzugt gemini-2.5-flash) | `AIza...` Key, Billing erforderlich |

- Die KI beginnt **immer mit der 48h-Prognose + Handlungsempfehlung**, gefolgt von der detaillierten Analyse (Elliott, EMA, RSI, MACD, Fundamentals, Gesamtbild)
- Das verwendete Modell wird in der Analysekarte angezeigt (`ANALYSE · MODELLNAME`)
- Gemini erkennt automatisch verfügbare Modelle via API — keine manuelle Modellpflege nötig

**Gemini Hinweise:**
- Benötigt Google Cloud Billing (Pay-as-you-go) — Free Tier hat Quota 0 für neue Projekte
- Billing aktivieren: console.cloud.google.com → Abrechnung → Abrechnungskonto verknüpfen
- API-Key aus Google Cloud Console → Credentials → API-Schlüssel erstellen (Einschränkung: Gemini API)
- Kosten minimal: Gemini 2.5 Flash ~$0.15 pro 1M Token

### Darstellung
- Gestylte Karte pro Asset: dunkler Header, Prognose-Banner, Kursziel-Boxen, Indikatortabelle
- 48h-Prognose prominent hervorgehoben (vor der Detailanalyse)
- Verwendetes KI-Modell als Label über der Analyse
- Fundamentaldaten bei Aktien (via Finnhub)

### E-Mail
- Optionaler Versand nach der Analyse
- Gleiches HTML-Format wie App-Darstellung inkl. Modell-Label
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
| Yahoo Finance v8 | Aktien & Edelmetalle OHLC, Fallback für custom Coins | kostenlos |
| Kraken Public API | BTC, XRP & custom Coins OHLC (Daily) | kostenlos |
| Finnhub | Fundamentaldaten, Ticker-Suche | kostenlos (Free Tier) |

---

## Versionshistorie

| Version | Änderung |
|---------|----------|
| 2.14.0 | Verwendetes KI-Modell in der Analysekarte anzeigen |
| 2.13.0 | Gemini maxOutputTokens 8000; Prompt ohne Einleitung/Begrüßung |
| 2.10.0 | Gemini Modelle auf 2.5-flash / 2.0-flash-001 aktualisiert (2.0-flash deprecated) |
| 2.8.0 | Gemini erkennt verfügbare Modelle automatisch via API |
| 2.7.0 | Gemini v1+v1beta Fallback; detaillierte Fehlermeldungen |
| 2.5.0 | Kraken als primäre Quelle für custom Coins; Yahoo Finance als Fallback |
| 2.2.0 | Gemini HTTP-Fehlerdetails aus Response-Body; genaue Fehlerbeschreibung |
| 2.1.0 | Krypto-Freifeld für beliebige Coins |
| 2.0.0 | Gemini-Prompt reduziert; alle Checkboxen leer per Standard |
| 1.9.0 | Gemini 429: Fallback auf nächstes Modell |
| 1.8.0 | Schlüsselwörter farbig, Erklärungstext schwarz; iframe-Höhe 5000 |
| 1.7.0 | 48h-Prognose zuerst im Prompt; vollständiger Markdown-Konverter; max_tokens 4000 |
| 1.6.0 | 48h-Prognose vor Detailanalyse; `##`/`**` durch HTML ersetzt |
| 1.3.0 | render_card() = bewährtes E-Mail-Format; Gemini → gemini-2.0-flash |
| 1.0.0 | Initiale Version: Aktien + Krypto + Edelmetalle vereint |

---

*Keine Anlageberatung — automatisch generierte technische Analyse.*
