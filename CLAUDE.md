# Markt Analyse — Claude Code Projektkontext

## Projektbeschreibung
Streamlit-App für tägliche technische Analysen von Aktien, Krypto und Edelmetallen mit KI-Unterstützung (Claude / Gemini) und optionalem E-Mail-Versand.

**Aktuelle Version:** 2.22.0  
**Deployment:** Streamlit Cloud → `anakinsky33/markt-analyse`, Branch `main`, File `app.py`

---

## Wichtige Dateien

| Datei | Beschreibung |
|-------|-------------|
| `app.py` | Hauptdatei — gesamte App-Logik |
| `requirements.txt` | `streamlit>=1.32.0`, `pandas>=2.0.0`, `anthropic>=0.40.0` |
| `.streamlit/config.toml` | `[server] headless = true` |
| `README.md` | Projektdokumentation |
| `CLAUDE.md` | Diese Datei |

---

## Architektur (app.py)

### Datenabruf
- `fetch_yahoo(symbol, days, interval)` — Aktien & Edelmetalle via Yahoo Finance v8; `interval="1d"` oder `"1wk"`
- `fetch_kraken(pair, kraken_key, days, interval_min)` — BTC & XRP via Kraken; `interval_min=1440` (täglich) oder `10080` (wöchentlich)
- `fetch_kraken_coin(coin, days, interval_min)` — Custom Coins via Kraken
- `fetch_coincap(coin, days)` — Custom Coins via CoinCap API (nur Tageskerzen, `d1`)
- `resample_weekly(raw)` — aggregiert Tageskerzen zu Wochenkerzen (letzter Schlusskurs der Woche)
- Fallback-Kette custom Coins: Kraken → CoinCap (ggf. resample) → Yahoo Finance

### Technische Indikatoren
- `build(raw)` — berechnet EMA50, EMA200, RSI(14), MACD aus Rohdaten
- `generate_prognose(data)` — regelbasierte Bull/Bear-Prognose

### KI-Analyse
- `_build_prompt(name, typ, data, fund, prog, history_days=30, short=False)` — gemeinsamer Prompt für beide KI-Anbieter
- `ai_claude(...)` → gibt `(text, "claude-haiku-4-5")` zurück
- `ai_gemini(...)` → erkennt verfügbare Modelle automatisch via `/v1beta/models?key=...`, bevorzugt `gemini-2.5-flash`; gibt `(text, modellname)` zurück

### Darstellung
- `render_card(name, typ, einheit, data, prog, fund, analyse_text, ai_modell="", horizont="täglich")` — einheitliches HTML für App (iframe) und E-Mail
- `_lines_to_html(lines)` + `_inline(t)` — Markdown-zu-HTML Konverter
- `_chart_ctx(data, horizont)` — gemeinsamer Setup-Kontext für alle Charts (Skalierung, Hilfsfunktionen)
- `_chart_ema(data, horizont)` → SVG Kurs + EMA 50/200
- `_chart_rsi(data, horizont)` → SVG RSI(14) mit Zonen
- `_chart_macd(data, horizont)` → SVG MACD-Histogramm + Linien
- `_make_charts(data, horizont)` → alle drei Charts gruppiert (Fallback bei regelbasierter Analyse)
- Charts erscheinen direkt nach der jeweiligen KI-Analyse-Sektion (EMA/RSI/MACD-Matching per Keyword)

---

## Datenquellen

| Quelle | Verwendung |
|--------|-----------|
| Yahoo Finance v8 | Aktien, Edelmetalle, 3. Fallback custom Coins |
| Kraken Public API | BTC, XRP, custom Coins (primär) |
| CoinCap API | custom Coins (2. Fallback, breite Abdeckung) |
| Finnhub (optional) | Fundamentaldaten, Ticker-Suche |

---

## Git & Deployment

**Push-Befehl** (lokaler Proxy blockiert Standard-Push, daher PAT direkt):
```bash
git -c commit.gpgsign=false commit -m "..."
git push https://anakinsky33:GITHUB_PAT@github.com/anakinsky33/markt-analyse.git main
```

**Merge-Commit** (bei divergiertem Remote):
```bash
git -c commit.gpgsign=false merge origin/main -m "Merge"
```

**Streamlit Cloud** aktualisiert automatisch nach jedem Push auf `main`.

---

## Secrets (Streamlit Cloud App-Einstellungen)

```toml
ANTHROPIC_API_KEY  = "sk-ant-..."
GOOGLE_AI_KEY      = "AIza..."
FINNHUB_API_KEY    = "..."
GMAIL_ABSENDER     = "deine@gmail.com"
GMAIL_APP_PASSWORT = "xxxx xxxx xxxx xxxx"
EMPFAENGER         = "empfaenger@mail.com"
```

Sidebar-Sichtbarkeit der Secrets:

| Secret | Sidebar sichtbar? |
|--------|------------------|
| `ANTHROPIC_API_KEY` | Ja (Passwort-Feld) |
| `GOOGLE_AI_KEY` | Ja (Passwort-Feld) |
| `FINNHUB_API_KEY` | Nein — nur aus Secrets |
| `GMAIL_ABSENDER` | Nein — nur aus Secrets |
| `GMAIL_APP_PASSWORT` | Nein — nur aus Secrets |
| `EMPFAENGER` | Ja (editierbares Textfeld, vorausgefüllt aus Secret) |

---

## Wichtige Konventionen

- **Versionsnummer** (`APP_VERSION`) bei jeder Änderung hochzählen (aktuell 2.22.0)
- `render_card()` ist die einzige Darstellungsfunktion — gilt für App und E-Mail
- Gemini-Modelle werden automatisch erkannt — keine manuelle Modellpflege nötig
- `commit.gpgsign=false` immer als `-c` Flag übergeben (globale Signing-Config blockiert sonst)
