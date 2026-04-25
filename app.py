#!/usr/bin/env python3
import streamlit as st
import os, json, datetime, urllib.request, urllib.parse, urllib.error, time, smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

APP_VERSION = "2.21.0"

st.set_page_config(page_title="Markt Analyse", page_icon="📊", layout="wide")

def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")

# ── Asset-Definitionen ─────────────────────────────────────────────────────────
FESTE_ASSETS = {
    "₿ Krypto": [
        {"name": "Bitcoin", "symbol": "BTC", "pair": "XBTUSD", "kraken": "XXBTZUSD", "typ": "krypto", "einheit": "USD"},
        {"name": "XRP",     "symbol": "XRP", "pair": "XRPUSD", "kraken": "XXRPZUSD", "typ": "krypto", "einheit": "USD"},
    ],
    "🥇 Edelmetalle": [
        {"name": "Gold",   "symbol": "GC=F", "typ": "metall", "einheit": "USD/oz"},
        {"name": "Silber", "symbol": "SI=F", "typ": "metall", "einheit": "USD/oz"},
    ],
}

YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com/",
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Markt Analyse")

    ausgewaehlt = []

    # Aktien: S&P 500 fest + freie Eingabe
    st.subheader("📈 Aktien")
    if st.checkbox("S&P 500 (^GSPC)", value=False, key="sp500"):
        ausgewaehlt.append({"name": "S&P 500", "symbol": "^GSPC", "typ": "aktie", "einheit": "Punkte"})

    aktien_eingabe = st.text_input(
        "Ticker eingeben (kommagetrennt)",
        placeholder="z.B. NVDA, AAPL, SAP.DE",
        help="Yahoo Finance Ticker — z.B. NVDA, AAPL, SAP.DE, SQ",
    )
    for ticker in [t.strip().upper() for t in aktien_eingabe.split(",") if t.strip()]:
        ausgewaehlt.append({"name": ticker, "symbol": ticker, "typ": "aktie", "einheit": "USD"})

    with st.expander("🔍 Ticker suchen (Firmenname)"):
        such_name = st.text_input("Firmenname", placeholder="z.B. Block, Siemens, Tesla", key="suche")
        such_key  = get_secret("FINNHUB_API_KEY")
        if such_name and such_key:
            try:
                url = f"https://finnhub.io/api/v1/search?q={urllib.parse.quote(such_name)}&token={such_key}"
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=10) as r:
                    res = json.loads(r.read())
                treffer = [x for x in res.get("result",[]) if x.get("type") in ("Common Stock","EQS")][:6]
                if treffer:
                    for t in treffer:
                        st.markdown(f"**{t['displaySymbol']}** — {t['description']}")
                else:
                    st.info("Keine Treffer")
            except Exception as e:
                st.warning(f"Suche fehlgeschlagen: {e}")
        elif such_name:
            st.caption("Finnhub-Key wird für die Suche benötigt.")

    # Krypto & Edelmetalle
    for kat, assets in FESTE_ASSETS.items():
        st.subheader(kat)
        for a in assets:
            if st.checkbox(a["name"], value=False, key=a["symbol"]):
                ausgewaehlt.append(a)
        if kat == "₿ Krypto":
            krypto_eingabe = st.text_input(
                "Weitere Coins (kommagetrennt)",
                placeholder="z.B. ETH, SOL, DOGE",
                help="Coin-Symbol eingeben — Daten via Yahoo Finance ({COIN}-USD)",
                key="krypto_extra",
            )
            for coin in [c.strip().upper() for c in krypto_eingabe.split(",") if c.strip()]:
                ausgewaehlt.append({"name": coin, "symbol": f"{coin}-USD", "typ": "krypto", "einheit": "USD", "yahoo_krypto": True})

    st.divider()

    finnhub_key = get_secret("FINNHUB_API_KEY")

    st.markdown("**📅 Analysehorizont**")
    horizont = st.radio(
        "Zeitrahmen",
        ["📆 Täglich (48h-Prognose)", "📅 Wöchentlich (7-Tage-Prognose)"],
        index=0,
        label_visibility="collapsed",
    )
    ist_woechentlich = "Wöchentlich" in horizont

    st.markdown("**🤖 KI-Analyse**")
    ai_modus = st.radio(
        "Anbieter",
        ["📊 Regelbasiert", "🔵 Claude (Anthropic)", "🟢 Gemini (Google)"],
        index=0,
    )
    if "Claude" in ai_modus:
        ai_key = st.text_input("Anthropic API Key", value=get_secret("ANTHROPIC_API_KEY"),
                               type="password", placeholder="sk-ant-...")
    elif "Gemini" in ai_modus:
        ai_key = st.text_input("Google AI Key", value=get_secret("GOOGLE_AI_KEY"),
                               type="password", placeholder="AIza...")
    else:
        ai_key = ""

    st.divider()

    # E-Mail
    st.subheader("📧 E-Mail")
    send_mail = st.toggle("Analyse per Mail senden", value=False)
    gmail_absender = get_secret("GMAIL_ABSENDER")
    gmail_passwort = get_secret("GMAIL_APP_PASSWORT")
    empfaenger     = st.text_input("Empfänger", value=get_secret("EMPFAENGER"))

# ── Hauptbereich Header ────────────────────────────────────────────────────────
st.title("📊 Markt Analyse")
st.caption(f"Aktien · Krypto · Edelmetalle  |  Elliott Wave · RSI · MACD · EMA · KI-Analyse · 48h-Prognose  |  v{APP_VERSION}")

if not ausgewaehlt:
    st.warning("Bitte mindestens ein Asset auswählen.")
    st.stop()

# ── Datenabruf ─────────────────────────────────────────────────────────────────
def fetch_yahoo(symbol, days=400, interval="1d"):
    now   = datetime.datetime.now(datetime.timezone.utc)
    end   = int(now.timestamp())
    start = int((now - datetime.timedelta(days=days)).timestamp())
    url   = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
             f"?interval={interval}&period1={start}&period2={end}")
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    results = data["chart"].get("result") or []
    if not results:
        err = data["chart"].get("error") or {}
        raise Exception(err.get("description") or f"Kein Ergebnis für {symbol}")
    result = results[0]
    timestamps = result.get("timestamp")
    if not timestamps:
        raise Exception(f"Kein Zeitreihen-Daten für {symbol} (Yahoo Format geändert)")
    closes = result["indicators"]["quote"][0]["close"]
    return [{"date": datetime.date.fromtimestamp(ts).isoformat(), "close": round(float(c), 4)}
            for ts, c in zip(timestamps, closes)
            if c is not None and c > 0]

def fetch_coincap(coin, days=400):
    search_url = f"https://api.coincap.io/v2/assets?search={urllib.parse.quote(coin.lower())}&limit=5"
    req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        assets = json.loads(r.read()).get("data", [])
    match = next((a for a in assets if a["symbol"].upper() == coin.upper()), None) or (assets[0] if assets else None)
    if not match:
        raise Exception(f"'{coin}' nicht auf CoinCap gefunden")
    coin_id = match["id"]
    now_ms  = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    start_ms = now_ms - days * 86400 * 1000
    hist_url = f"https://api.coincap.io/v2/assets/{coin_id}/history?interval=d1&start={start_ms}&end={now_ms}"
    req = urllib.request.Request(hist_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        prices = json.loads(r.read()).get("data", [])
    if not prices:
        raise Exception(f"Keine Preisdaten für {coin_id} auf CoinCap")
    return [{"date": datetime.datetime.fromtimestamp(int(p["time"]) // 1000, datetime.timezone.utc).date().isoformat(),
             "close": round(float(p["priceUsd"]), 8)}
            for p in prices]

def resample_weekly(raw):
    """Aggregiert Tageskerzen zu Wochenkerzen (letzter Schlusskurs der Woche)."""
    weekly = {}
    for candle in raw:
        date = datetime.date.fromisoformat(candle["date"])
        week_key = date.isocalendar()[:2]  # (year, week_number)
        weekly[week_key] = candle
    return sorted(weekly.values(), key=lambda x: x["date"])

def fetch_kraken_coin(coin, days=720, interval_min=1440):
    pair  = coin.upper() + "USD"
    since = int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).timestamp())
    url   = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval_min}&since={since}"
    req   = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    if data.get("error") and data["error"]:
        raise Exception(f"Kraken Pair {pair} unbekannt: {data['error']}")
    keys = [k for k in data.get("result", {}) if k != "last"]
    if not keys:
        raise Exception(f"Keine Daten für {pair} auf Kraken")
    candles = data["result"][keys[0]]
    if not candles:
        raise Exception(f"Leere Datenreihe für {pair} auf Kraken")
    return [{"date": datetime.date.fromtimestamp(int(c[0])).isoformat(), "close": round(float(c[4]), 8)}
            for c in candles if float(c[4]) > 0]

def fetch_kraken(pair, kraken_key, days=720, interval_min=1440):
    since = int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).timestamp())
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval_min}&since={since}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    if data.get("error"):
        raise Exception(f"Kraken: {data['error']}")
    candles = data["result"][kraken_key]
    return [{"date": datetime.date.fromtimestamp(int(c[0])).isoformat(), "close": float(c[4])}
            for c in candles if float(c[4]) > 0]

def fetch_fundamentals(symbol, api_key):
    if not api_key or symbol.startswith("^"):
        return {}
    try:
        h = {"User-Agent": "Mozilla/5.0", "X-Finnhub-Token": api_key}
        url1 = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={api_key}"
        with urllib.request.urlopen(urllib.request.Request(url1, headers=h), timeout=15) as r:
            raw = json.loads(r.read())
        if "error" in raw:
            return {"_error": raw["error"]}
        m = raw.get("metric", {})
        url2 = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}"
        with urllib.request.urlopen(urllib.request.Request(url2, headers=h), timeout=15) as r:
            prof = json.loads(r.read())
        mc = prof.get("marketCapitalization")
        return {
            "_name":          prof.get("name"),
            "marketCap":      mc * 1e6 if mc else None,
            "trailingPE":     m.get("peTTM"),
            "forwardPE":      m.get("peNormalizedAnnual"),
            "priceToBook":    m.get("pbQuarterly"),
            "trailingEps":    m.get("epsBasicExclExtraItemsTTM"),
            "dividendYield":  m.get("dividendYieldIndicatedAnnual") / 100 if m.get("dividendYieldIndicatedAnnual") else None,
            "revenueGrowth":  m.get("revenueGrowthTTMYoy") / 100 if m.get("revenueGrowthTTMYoy") else None,
            "earningsGrowth": m.get("epsGrowthTTMYoy") / 100 if m.get("epsGrowthTTMYoy") else None,
            "profitMargins":  m.get("netProfitMarginTTM") / 100 if m.get("netProfitMarginTTM") else None,
            "returnOnEquity": m.get("roeTTM") / 100 if m.get("roeTTM") else None,
            "debtToEquity":   m.get("totalDebt/totalEquityQuarterly"),
            "week52High":     m.get("52WeekHigh"),
            "week52Low":      m.get("52WeekLow"),
        }
    except Exception as e:
        return {"_error": str(e)}

# ── Technische Indikatoren ─────────────────────────────────────────────────────
def ema(prices, period):
    k = 2/(period+1); out=[]; prev=None
    for i, p in enumerate(prices):
        if i < period-1: out.append(None); continue
        if prev is None: prev = sum(prices[:period])/period
        else: prev = p*k + prev*(1-k)
        out.append(round(prev, 6))
    return out

def rsi(prices, period=14):
    out=[None]*period; ag=al=0.0
    for i in range(1, period+1):
        d = prices[i]-prices[i-1]
        if d > 0: ag += d
        else: al -= d
    ag /= period; al /= period
    out.append(round(100 if al==0 else 100-100/(1+ag/al), 2))
    for i in range(period+1, len(prices)):
        d = prices[i]-prices[i-1]
        ag = (ag*(period-1)+max(d,0))/period
        al = (al*(period-1)+max(-d,0))/period
        out.append(round(100 if al==0 else 100-100/(1+ag/al), 2))
    return out

def macd(prices):
    e12=ema(prices,12); e26=ema(prices,26)
    ml=[round(e12[i]-e26[i],6) if e12[i] and e26[i] else None for i in range(len(prices))]
    st_=next(i for i,x in enumerate(ml) if x is not None)
    sr=ema([x for x in ml if x is not None],9)
    sig=[None if ml[i] is None else sr[i-st_] for i in range(len(prices))]
    hist=[round(ml[i]-sig[i],6) if ml[i] is not None and sig[i] is not None else None for i in range(len(prices))]
    return ml, sig, hist

def build(raw):
    prices=[r["close"] for r in raw]
    e50,e200=ema(prices,50),ema(prices,200)
    r14=rsi(prices); ml,sig,hist=macd(prices)
    return [{"date":raw[i]["date"],"price":raw[i]["close"],
             "ema50":e50[i],"ema200":e200[i],
             "rsi":r14[i],"macd":ml[i],"signal":sig[i],"hist":hist[i]}
            for i in range(len(raw))]

def generate_prognose(data):
    last=data[-1]; sb=[]; se=[]
    p,e50,e200=last["price"],last["ema50"] or 0,last["ema200"] or 0
    if p>e50>e200:   sb.append("Golden Cross: Preis über EMA50 & EMA200")
    elif p<e50<e200: se.append("Death Cross: Preis unter EMA50 & EMA200")
    elif p>e50:      sb.append("Preis über EMA50")
    else:            se.append("Preis unter EMA50")
    r=last["rsi"] or 50
    if r>70:   se.append(f"RSI überkauft ({r})")
    elif r<30: sb.append(f"RSI überverkauft – Erholung möglich ({r})")
    elif r>55: sb.append(f"RSI bullish ({r})")
    elif r<45: se.append(f"RSI bearish ({r})")
    if last["macd"] is not None and last["signal"] is not None:
        if last["macd"]>last["signal"]: sb.append("MACD über Signal-Linie")
        else:                           se.append("MACD unter Signal-Linie")
    if len(data)>=3:
        h1,h2=last["hist"],data[-2]["hist"]
        if h1 and h2:
            if h1>h2: sb.append("Histogramm steigt – Momentum aufbauend")
            else:     se.append("Histogramm fällt – Momentum nachlassend")
    if len(data)>=4:
        t3=data[-1]["price"]-data[-4]["price"]
        if t3>0: sb.append(f"3-Tage-Impuls positiv (+{t3:.2f})")
        else:    se.append(f"3-Tage-Impuls negativ ({t3:.2f})")
    nb,nd=len(sb),len(se); total=max(nb+nd,1)
    bull=round(nb/total*100); bear=100-bull; main_bull=bull>=bear
    recent=[d["price"] for d in data[-10:]]
    atr=(max(recent)-min(recent))/len(recent)
    return {
        "main_bull":main_bull,"bull_pct":bull,"bear_pct":bear,
        "target_main": p+atr*1.5 if main_bull else p-atr*1.5,
        "target_alt":  p-atr    if main_bull else p+atr,
        "inval":       p-atr*2  if main_bull else p+atr*2,
        "signals_bull":sb,"signals_bear":se,"current":p,"atr":atr,
        "empfehlung": ("Vorsichtiger Long-Aufbau möglich" if bull>=70
                       else "Kein Long-Einstieg empfohlen" if bear>=70
                       else "Abwarten auf Bestätigung"),
    }

# ── KI-Analyse ─────────────────────────────────────────────────────────────────
def _build_prompt(name, typ, data, fund, prog, history_days=30, short=False, horizont="täglich"):
    last = data[-1]
    def fp(v): return f"{v:.4f}" if v else "—"
    def px(v): return f"{v:,.4f}" if v else "—"
    def pct(v): return f"{v*100:.1f}%" if v else "—"
    f = fund or {}

    ist_woechentlich = horizont == "wöchentlich"
    zeiteinheit = "WOCHEN" if ist_woechentlich else "TAGE"
    prognose_titel = "7-Tage-Prognose (1 Woche)" if ist_woechentlich else "2-Tages-Prognose (48h)"
    prognose_hinweis = "1-Wochen" if ist_woechentlich else "48h"
    kerzen_typ = "Wochenkerzen" if ist_woechentlich else "Tageskerzen"

    history = "\n".join(
        f"  {d['date']}: {px(d['price'])} | RSI:{d['rsi']} | MACD:{d['macd']} | Hist:{d['hist']}"
        for d in data[-history_days:]
    )

    fund_block = ""
    if typ == "aktie" and f:
        fund_block = f"""
FUNDAMENTALDATEN:
- Marktkapitalisierung: {f.get('marketCap') and f'${f["marketCap"]/1e9:.1f}B' or '—'}
- KGV (TTM): {fp(f.get('trailingPE'))} | KGV Forward: {fp(f.get('forwardPE'))} | EPS: {fp(f.get('trailingEps'))}
- Kurs/Buchwert: {fp(f.get('priceToBook'))} | Verschuldungsgrad: {fp(f.get('debtToEquity'))}
- Gewinnmarge: {pct(f.get('profitMargins'))} | ROE: {pct(f.get('returnOnEquity'))}
- Umsatzwachstum: {pct(f.get('revenueGrowth'))} | Gewinnwachstum: {pct(f.get('earningsGrowth'))}
- Dividendenrendite: {pct(f.get('dividendYield'))}
- 52W-Hoch: {fp(f.get('week52High'))} | 52W-Tief: {fp(f.get('week52Low'))}"""

    system_map = {
        "aktie":  f"Du bist ein erfahrener Aktienanalyst mit Expertise in Elliott-Wellen, RSI, MACD und EMAs. Analysiere {name} auf Basis von {kerzen_typ} präzise und meinungsstark auf Deutsch. Nenne immer konkrete Kurslevels.",
        "krypto": f"Du bist ein erfahrener Kryptoanalyst mit Expertise in Elliott-Wellen, RSI, MACD und EMAs. Analysiere {name}/USD auf Basis von {kerzen_typ} präzise und meinungsstark auf Deutsch. Nenne immer konkrete Kurslevels in USD.",
        "metall": f"Du bist ein erfahrener Edelmetall-Analyst mit Expertise in Elliott-Wellen, RSI, MACD und EMAs. Analysiere {name} auf Basis von {kerzen_typ} präzise und meinungsstark auf Deutsch. Nenne immer konkrete Preislevels in USD pro Unze.",
    }
    system = system_map.get(typ, f"Du bist ein erfahrener Finanzanalyst. Analysiere {name} auf Deutsch.")
    trend = "BULLISCH" if prog["main_bull"] else "BÄRISCH"
    sektion5 = (
        "## 5. Fundamentale Bewertung\nBewerte KGV, Wachstum, Margen und Verschuldung im Branchenvergleich."
        if typ == "aktie" else
        "## 5. Marktsentiment & Makrofaktoren\nWas treibt den Markt aktuell? Welche externen Faktoren sind relevant?"
    )

    kompakt = "\nAntworte kompakt und präzise, maximal 500 Wörter insgesamt." if short else ""

    return f"""{system}

AKTUELL ({last['date']}) — {kerzen_typ.upper()}:
- Kurs:    {px(last['price'])}
- EMA 50:  {px(last['ema50'])}
- EMA 200: {px(last['ema200'])}
- RSI(14): {fp(last['rsi'])}
- MACD:    {fp(last['macd'])} | Signal: {fp(last['signal'])} | Histogramm: {fp(last['hist'])}
- Regelbasierter Trend: {trend} ({prog['bull_pct']}% Bull / {prog['bear_pct']}% Bear)
{fund_block}

LETZTE {history_days} {zeiteinheit}:
{history}

Antworte OHNE Markdown-Tabellen, OHNE Code-Blöcke, OHNE --- Trennlinien. Nur Fliesstext und Aufzählungen.{kompakt}
Beginne DIREKT mit "## 1." — KEINE Einleitung, KEIN Begrüßungssatz, KEIN Vorwort.

## 1. {prognose_titel}
- HAUPTSZENARIO (XX% Wahrscheinlichkeit): Konkreter Kursverlauf mit Zielkurs und % Veränderung.
- ALTERNATIVSZENARIO (XX% Wahrscheinlichkeit): Gegenszenario mit Kursziel.
- ENTSCHEIDENDE MARKEN: Welche Levels bestimmen das Szenario?
- INVALIDIERUNGSLEVEL: Ab welchem Kurs wird das Hauptszenario ungültig?
- HANDLUNGSEMPFEHLUNG: Klar und direkt für den {prognose_hinweis}-Horizont.

## 2. Elliott-Wellen-Analyse
Aktive Welle? Impuls oder Korrektur? Position im Zyklus?

## 3. EMA-Trendstruktur
Preis vs. EMA50 vs. EMA200. Golden Cross / Death Cross? Trendstärke?

## 4. RSI-Analyse
Momentum, überkauft/überverkauft, Divergenzen?

## 5. MACD-Analyse
Crossover, Histogramm-Richtung, Momentum-Veränderung?

{sektion5}

## 7. Gesamtbild & Schlüsselniveaus
Übergeordneter Bias + konkrete Support- und Resistance-Zonen."""

def ai_claude(name, typ, data, fund, prog, key, horizont="täglich"):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            messages=[{"role":"user","content":_build_prompt(name,typ,data,fund,prog,horizont=horizont)}],
        )
        return msg.content[0].text, "claude-haiku-4-5"
    except Exception as e:
        return f"⚠️ Claude-Fehler: {e}", "claude-haiku-4-5"

def ai_gemini(name, typ, data, fund, prog, key, horizont="täglich"):
    prompt = _build_prompt(name, typ, data, fund, prog, horizont=horizont)
    body = json.dumps({"contents":[{"parts":[{"text":prompt}]}],
                       "generationConfig":{"maxOutputTokens":8000,"temperature":0.7}}).encode()

    # Verfügbare Modelle abfragen
    available_models = []
    for api_ver in ["v1beta", "v1"]:
        try:
            list_url = f"https://generativelanguage.googleapis.com/{api_ver}/models?key={key}"
            req = urllib.request.Request(list_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                mlist = json.loads(r.read())
            for m in mlist.get("models", []):
                n = m.get("name","").replace("models/","")
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    available_models.append((n, api_ver))
            if available_models:
                break
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
            except Exception:
                detail = str(e)
            if e.code in (401, 403):
                return f"⚠️ Gemini: API-Key ungültig oder keine Berechtigung ({e.code}): {detail}", ""
            if e.code != 404:
                return f"⚠️ Gemini: Modellliste-Fehler ({e.code}): {detail}", ""
        except Exception as e:
            return f"⚠️ Gemini: Verbindungsfehler: {e}", ""

    if not available_models:
        return "⚠️ Gemini: Keine Modelle gefunden. Bitte prüfe ob die Generative Language API im Google Cloud Projekt aktiviert ist.", ""

    # Bevorzugte Modelle zuerst versuchen
    preferred = ["gemini-2.5-flash", "gemini-2.0-flash-001", "gemini-2.0-flash-lite-001", "gemini-2.5-pro"]
    ordered = sorted(available_models, key=lambda x: next((i for i,p in enumerate(preferred) if p in x[0]), 99))

    for model, api_ver in ordered[:4]:
        try:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={key}"
            req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                resp = json.loads(r.read())
            return resp["candidates"][0]["content"]["parts"][0]["text"], model
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
            except Exception:
                detail = ""
            if e.code == 429:
                return f"⚠️ Gemini: Rate-Limit ({model}) — {detail or 'bitte warten und erneut versuchen'}", model
            return f"⚠️ Gemini-Fehler ({e.code}, {model}): {detail or e.reason}", model
        except Exception as e:
            return f"⚠️ Gemini-Fehler ({model}): {e}", model

    return f"⚠️ Gemini: Alle Modelle fehlgeschlagen. Verfügbar: {[m for m,_ in available_models[:5]]}", ""

# ── Darstellung (identisch mit bewährtem E-Mail-Format) ───────────────────────
ASSET_FARBEN = {"aktie": "#1a73e8", "krypto": "#f7931a", "metall": "#FFD700"}

def _chart_ctx(data, horizont):
    n   = 52 if horizont == "wöchentlich" else 60
    pts = data[-n:]
    total = len(pts)
    W = 620; PL, PR, PT, PB = 50, 14, 14, 18; pw = W - PL - PR
    lbl = "font-family:Arial,sans-serif;font-size:9px"
    def xs(i): return PL + i / max(total-1, 1) * pw
    def ny(v, lo, hi, H):
        return PT+(1-(v-lo)/(hi-lo))*(H-PT-PB) if hi != lo else PT+(H-PT-PB)/2
    def pline(vals, lo, hi, H, color, width=1.5):
        segs = [(xs(i), ny(v,lo,hi,H)) for i,v in enumerate(vals) if v is not None]
        if len(segs) < 2: return ""
        d = " ".join(f"{'M' if j==0 else 'L'}{x:.1f},{y:.1f}" for j,(x,y) in enumerate(segs))
        return f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
    def fmt(v):
        av = abs(v)
        if av >= 1000: return f"{v:,.0f}"
        if av >= 10:   return f"{v:.1f}"
        if av >= 1:    return f"{v:.2f}"
        if av >= 0.01: return f"{v:.4f}"
        return f"{v:.6f}"
    def xlbls(H):
        step = max(1, total//5); out = ""
        for i in range(0, total, step):
            out += f'<text x="{xs(i):.1f}" y="{H-4}" style="{lbl};fill:#555" text-anchor="middle">{pts[i]["date"][5:]}</text>'
        return out
    return pts, total, W, PL, PR, PT, PB, pw, lbl, xs, ny, pline, fmt, xlbls

def _chart_ema(data, horizont="täglich"):
    pts, total, W, PL, PR, PT, PB, pw, lbl, xs, ny, pline, fmt, xlbls = _chart_ctx(data, horizont)
    if total < 5: return ""
    H = 145
    prices = [p["price"] for p in pts]; e50 = [p["ema50"] for p in pts]; e200 = [p["ema200"] for p in pts]
    all1 = [v for v in prices+e50+e200 if v is not None]
    lo, hi = min(all1), max(all1); mg = (hi-lo)*0.06 or abs(lo)*0.01 or 1; lo -= mg; hi += mg
    grid = ""
    for t in [0.15, 0.5, 0.85]:
        v = lo+t*(hi-lo); y = ny(v,lo,hi,H)
        grid += f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#1e2d3d" stroke-width="0.6"/>'
        grid += f'<text x="{PL-3}" y="{y+3:.1f}" style="{lbl};fill:#555" text-anchor="end">{fmt(v)}</text>'
    return f'''<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;background:#0f1923">
      {grid}{pline(e200,lo,hi,H,"#e74c3c",1.4)}{pline(e50,lo,hi,H,"#3498db",1.4)}{pline(prices,lo,hi,H,"#ecf0f1",1.9)}
      <text x="{PL+4}" y="{PT+10}" style="{lbl};fill:#888;font-weight:bold">Kurs + EMA</text>
      <line x1="{PL+68}" y1="{PT+6}" x2="{PL+80}" y2="{PT+6}" stroke="#ecf0f1" stroke-width="1.9"/>
      <text x="{PL+83}" y="{PT+10}" style="{lbl};fill:#aaa">Kurs</text>
      <line x1="{PL+106}" y1="{PT+6}" x2="{PL+118}" y2="{PT+6}" stroke="#3498db" stroke-width="1.4"/>
      <text x="{PL+121}" y="{PT+10}" style="{lbl};fill:#3498db">EMA 50</text>
      <line x1="{PL+155}" y1="{PT+6}" x2="{PL+167}" y2="{PT+6}" stroke="#e74c3c" stroke-width="1.4"/>
      <text x="{PL+170}" y="{PT+10}" style="{lbl};fill:#e74c3c">EMA 200</text>
      {xlbls(H)}</svg>'''

def _chart_rsi(data, horizont="täglich"):
    pts, total, W, PL, PR, PT, PB, pw, lbl, xs, ny, pline, fmt, xlbls = _chart_ctx(data, horizont)
    if total < 5: return ""
    H = 88
    rsi_vals = [p["rsi"] for p in pts]
    y70 = ny(70,0,100,H); y50 = ny(50,0,100,H); y30 = ny(30,0,100,H)
    last_rsi = next((v for v in reversed(rsi_vals) if v is not None), None)
    rsi_col  = "#e74c3c" if (last_rsi or 50)>70 else ("#27ae60" if (last_rsi or 50)<30 else "#f39c12")
    rsi_lbl  = (f'<text x="{W-PR+2}" y="{ny(last_rsi,0,100,H)+4:.1f}" style="{lbl};fill:{rsi_col};font-weight:bold">{last_rsi:.0f}</text>'
                if last_rsi else "")
    return f'''<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;background:#0f1923">
      <rect x="{PL}" y="{PT}" width="{pw}" height="{y70-PT:.1f}" fill="#e74c3c" opacity="0.08"/>
      <rect x="{PL}" y="{y30:.1f}" width="{pw}" height="{H-PB-y30:.1f}" fill="#27ae60" opacity="0.08"/>
      <line x1="{PL}" y1="{y70:.1f}" x2="{W-PR}" y2="{y70:.1f}" stroke="#e74c3c" stroke-width="0.7" stroke-dasharray="4,3"/>
      <line x1="{PL}" y1="{y50:.1f}" x2="{W-PR}" y2="{y50:.1f}" stroke="#444" stroke-width="0.5" stroke-dasharray="2,3"/>
      <line x1="{PL}" y1="{y30:.1f}" x2="{W-PR}" y2="{y30:.1f}" stroke="#27ae60" stroke-width="0.7" stroke-dasharray="4,3"/>
      <text x="{PL-3}" y="{y70+3:.1f}" style="{lbl};fill:#e74c3c" text-anchor="end">70</text>
      <text x="{PL-3}" y="{y50+3:.1f}" style="{lbl};fill:#555" text-anchor="end">50</text>
      <text x="{PL-3}" y="{y30+3:.1f}" style="{lbl};fill:#27ae60" text-anchor="end">30</text>
      {pline(rsi_vals,0,100,H,"#f39c12",1.6)}{rsi_lbl}
      <text x="{PL+4}" y="{PT+10}" style="{lbl};fill:#888;font-weight:bold">RSI (14)</text>
      {xlbls(H)}</svg>'''

def _chart_macd(data, horizont="täglich"):
    pts, total, W, PL, PR, PT, PB, pw, lbl, xs, ny, pline, fmt, xlbls = _chart_ctx(data, horizont)
    if total < 5: return ""
    H = 88
    macd_vals = [p["macd"] for p in pts]; signal_vals = [p["signal"] for p in pts]; hist_vals = [p["hist"] for p in pts]
    all3 = [v for v in macd_vals+signal_vals+hist_vals if v is not None]
    if not all3: return ""
    lo, hi = min(all3), max(all3); mg = (hi-lo)*0.12 or 0.0001; lo -= mg; hi += mg
    y0 = ny(0,lo,hi,H); bw = max(0.8, pw/total*0.72)
    hist_svg = ""
    for i, v in enumerate(hist_vals):
        if v is None: continue
        bx = xs(i)-bw/2; by = ny(v,lo,hi,H); col = "#27ae60" if v>=0 else "#e74c3c"
        if v >= 0: hist_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{max(y0-by,0):.1f}" fill="{col}" opacity="0.75"/>'
        else:      hist_svg += f'<rect x="{bx:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{max(by-y0,0):.1f}" fill="{col}" opacity="0.75"/>'
    grid = f'<line x1="{PL}" y1="{y0:.1f}" x2="{W-PR}" y2="{y0:.1f}" stroke="#555" stroke-width="0.8"/>'
    for t in [0.2, 0.8]:
        v = lo+t*(hi-lo); y = ny(v,lo,hi,H)
        if PT < y < H-PB:
            grid += f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#1e2d3d" stroke-width="0.5"/>'
            grid += f'<text x="{PL-3}" y="{y+3:.1f}" style="{lbl};fill:#555" text-anchor="end">{fmt(v)}</text>'
    return f'''<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;background:#0f1923">
      {grid}{hist_svg}{pline(macd_vals,lo,hi,H,"#3498db",1.3)}{pline(signal_vals,lo,hi,H,"#f39c12",1.3)}
      <text x="{PL+4}" y="{PT+10}" style="{lbl};fill:#888;font-weight:bold">MACD</text>
      <line x1="{PL+50}" y1="{PT+6}" x2="{PL+62}" y2="{PT+6}" stroke="#3498db" stroke-width="1.3"/>
      <text x="{PL+64}" y="{PT+10}" style="{lbl};fill:#3498db">MACD</text>
      <line x1="{PL+97}" y1="{PT+6}" x2="{PL+109}" y2="{PT+6}" stroke="#f39c12" stroke-width="1.3"/>
      <text x="{PL+112}" y="{PT+10}" style="{lbl};fill:#f39c12">Signal</text>
      {xlbls(H)}</svg>'''

def _make_charts(data, horizont="täglich"):
    c1 = _chart_ema(data, horizont); c2 = _chart_rsi(data, horizont); c3 = _chart_macd(data, horizont)
    if not (c1 or c2 or c3): return ""
    return f'<div style="margin:0;overflow:hidden">{c1}{c2}{c3}</div>'

def render_card(name, typ, einheit, data, prog, fund, analyse_text, ai_modell="", horizont="täglich"):
    last  = data[-1]
    farbe = ASSET_FARBEN.get(typ, "#888")
    trend_col = "#27ae60" if prog["main_bull"] else "#e74c3c"
    trend_txt = "📈 BULLISCH" if prog["main_bull"] else "📉 BÄRISCH"
    p = prog["current"]
    pct_main = (prog["target_main"] - p) / p * 100
    pct_alt  = (prog["target_alt"]  - p) / p * 100
    ema50_ok  = (last["price"] or 0) > (last["ema50"]  or 0)
    ema200_ok = (last["price"] or 0) > (last["ema200"] or 0)
    rsi_v     = last["rsi"] or 0
    rsi_status = "Überkauft" if rsi_v > 70 else ("Überverkauft" if rsi_v < 30 else "Neutral")
    def px(v): return f"{v:,.4f}" if v else "—"
    def gc(ok): return "#27ae60" if ok else "#e74c3c"
    def tc(v):  return "#27ae60" if (v or 0) > 0 else "#e74c3c"
    def rc(v):
        if not v: return "#888"
        return "#e74c3c" if v > 70 else ("#27ae60" if v < 30 else "#f39c12")

    kat_label = {"aktie": "AKTIEN ANALYSE", "krypto": "KRYPTO ANALYSE", "metall": "EDELMETALL ANALYSE"}.get(typ, "ANALYSE")
    horizont_label = "WEEKLY" if horizont == "wöchentlich" else "DAILY"

    # Fundamentals
    fund_rows = ""
    if typ == "aktie" and fund:
        def fp(v): return f"{v:.2f}" if v is not None else "—"
        def pct(v): return f"{v*100:.1f} %" if v is not None else "—"
        def mc(v): return (f"${v/1e12:.2f} T" if v >= 1e12 else f"${v/1e9:.2f} B") if v else "—"
        fund_rows = f"""
<tr><td colspan="3" style="background:#2c3e50;color:white;padding:8px 12px;font-size:11px;font-weight:bold;letter-spacing:1px">FUNDAMENTALDATEN</td></tr>
<tr style="background:white"><td style="padding:8px 12px;color:#555;font-size:13px">Marktkapitalisierung</td><td style="color:#333;font-weight:bold">{mc(fund.get("marketCap"))}</td><td></td></tr>
<tr style="background:#f9f9f9"><td style="padding:8px 12px;color:#555;font-size:13px">KGV Trailing / Forward</td><td style="color:#333;font-weight:bold">{fp(fund.get("trailingPE"))} / {fp(fund.get("forwardPE"))}</td><td></td></tr>
<tr style="background:white"><td style="padding:8px 12px;color:#555;font-size:13px">Gewinnmarge / ROE</td><td style="color:#333;font-weight:bold">{pct(fund.get("profitMargins"))} / {pct(fund.get("returnOnEquity"))}</td><td></td></tr>
<tr style="background:#f9f9f9"><td style="padding:8px 12px;color:#555;font-size:13px">52W-Hoch / Tief</td><td style="color:#333;font-weight:bold">{fp(fund.get("week52High"))} / {fp(fund.get("week52Low"))}</td><td></td></tr>"""

    # Analyse-Text: Markdown → HTML (vollständig)
    import html as hl, re

    def _inline(t):
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', t)
        t = re.sub(r'`([^`]+)`', r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;font-family:monospace;font-size:12px;color:#c0392b">\1</code>', t)
        return t

    def _lines_to_html(lines):
        out = []; in_code = False; table_hdr = True
        for line in lines:
            s = line.strip()
            if s.startswith("```"):
                if in_code: out.append("</pre>"); in_code = False
                else: out.append('<pre style="background:#f5f5f5;padding:10px;border-radius:4px;font-size:12px;color:#333;margin:6px 0;white-space:pre-wrap">'); in_code = True
                continue
            if in_code: out.append(hl.escape(line) + "\n"); continue
            if s.startswith("|") and "|" in s[1:]:
                if re.match(r'^\|[\s\-\:\|]+\|$', s):
                    table_hdr = False; continue
                cells = [c.strip() for c in s.split("|")[1:-1]]
                if table_hdr:
                    row = "".join(f'<th style="padding:5px 10px;background:#2c3e50;color:white;text-align:left;font-size:11px;font-weight:bold">{_inline(hl.escape(c.replace("**","")))}</th>' for c in cells)
                    out.append(f'<table style="width:100%;border-collapse:collapse;margin:8px 0;font-size:12px"><tr>{row}</tr>')
                else:
                    row = "".join(f'<td style="padding:5px 10px;border-bottom:1px solid #eee;color:#333">{_inline(hl.escape(c))}</td>' for c in cells)
                    out.append(f"<tr>{row}</tr>")
                continue
            else:
                if not table_hdr: out.append("</table>"); table_hdr = True
            if re.match(r'^[-\*_]{3,}$', s): continue
            if not s: continue
            if s.startswith("#### "): out.append(f'<p style="color:#555;font-weight:bold;font-size:12px;margin:10px 0 2px 0">{_inline(hl.escape(s[5:]))}</p>')
            elif s.startswith("### "): out.append(f'<p style="color:#2c3e50;font-weight:bold;font-size:13px;margin:12px 0 4px 0">{_inline(hl.escape(s[4:]))}</p>')
            elif s.startswith("## "):
                sec = s[3:]
                is_p = any(x in sec for x in ["48h","2-Tages","Prognose","1."])
                bc = "#e74c3c" if is_p else farbe; col = "#c0392b" if is_p else "#2c3e50"
                out.append(f'<p style="color:{col};font-weight:bold;font-size:14px;border-bottom:2px solid {bc};padding-bottom:4px;margin-top:18px">{hl.escape(sec)}</p>')
            elif s.startswith("# "): out.append(f'<p style="color:#1a1a2e;font-weight:bold;font-size:15px;margin-top:16px;border-bottom:2px solid {farbe};padding-bottom:4px">{hl.escape(s[2:])}</p>')
            else:
                kw = re.sub(r'^[\-\s\*]+', '', s)
                if any(kw.startswith(k) for k in ["HAUPTSZENARIO","ALTERNATIVSZENARIO"]):
                    label, sep, rest = kw.partition(":")
                    lbl_html = f'<strong style="color:#c0392b">{_inline(hl.escape("- " + label))}</strong>'
                    out.append(f'<p style="margin:5px 0">{lbl_html}{hl.escape(sep)}<span style="color:#333">{_inline(hl.escape(rest))}</span></p>')
                elif any(kw.startswith(k) for k in ["ENTSCHEIDENDE","INVALIDIERUNG","HANDLUNG"]):
                    label, sep, rest = kw.partition(":")
                    lbl_html = f'<strong style="color:#e67e22">{_inline(hl.escape("- " + label))}</strong>'
                    out.append(f'<p style="margin:5px 0">{lbl_html}{hl.escape(sep)}<span style="color:#333">{_inline(hl.escape(rest))}</span></p>')
                else:
                    out.append(f'<p style="margin:3px 0;color:#333;font-size:13px;line-height:1.6">{_inline(hl.escape(s))}</p>')
        if not table_hdr: out.append("</table>")
        if in_code: out.append("</pre>")
        return "".join(out)

    prognose_html = rest_html = ""
    if analyse_text:
        in_prog = False
        prog_lines, rest_lines = [], []
        for line in analyse_text.split("\n"):
            if line.strip().startswith("## "):
                sec = line.strip()[3:]
                in_prog = any(x in sec for x in ["1.", "48h", "2-Tages", "Prognose"])
            (prog_lines if in_prog else rest_lines).append(line)
        prognose_html = _lines_to_html(prog_lines)
        rest_html     = _lines_to_html(rest_lines)

    prognose_row = ""
    if prognose_html:
        prognose_row = f'<tr><td style="background:#fff8f0;padding:16px 20px;border-left:4px solid #e74c3c">{prognose_html}</td></tr>'

    # Charts nach Sektionen einbetten (mit KI-Text) oder gruppiert (regelbasiert)
    CHART_FNS = {"EMA": _chart_ema, "RSI": _chart_rsi, "MACD": _chart_macd}

    if rest_lines:
        # Sektionen aufteilen und Charts nach EMA/RSI/MACD-Sektionen einfügen
        modell_label = f'<div style="font-size:11px;color:#aaa;letter-spacing:1px;margin-bottom:10px">ANALYSE · {ai_modell.upper()}</div>' if ai_modell else ""
        sections = []; curr_hdr = None; curr_lines = []
        for line in rest_lines:
            if line.strip().startswith("## "):
                sections.append((curr_hdr, curr_lines)); curr_hdr = line.strip(); curr_lines = [line]
            else:
                curr_lines.append(line)
        sections.append((curr_hdr, curr_lines))

        rest_row = ""; first = True
        for hdr, lines in sections:
            if not any(l.strip() for l in lines) and not hdr:
                continue
            prefix = modell_label if first else ""
            first = False
            rest_row += f'<tr><td style="background:white;padding:20px">{prefix}{_lines_to_html(lines)}</td></tr>'
            if hdr:
                for key, fn in CHART_FNS.items():
                    if key in hdr.upper():
                        svg = fn(data, horizont)
                        if svg:
                            rest_row += f'<tr><td style="padding:0">{svg}</td></tr>'
                        break
    else:
        rest_row = ""

    # Gruppierte Charts nur wenn keine KI-Analyse (regelbasiert)
    charts_row = f'<tr><td style="padding:0">{_make_charts(data, horizont=horizont)}</td></tr>' if not analyse_text else ""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;margin:0 auto 30px auto;font-family:Arial,sans-serif;border-collapse:collapse">
  <tr><td style="background:#1a1a2e;padding:18px 20px;border-left:5px solid {farbe}">
    <div style="font-size:10px;color:#aaa;letter-spacing:2px;text-transform:uppercase">{kat_label} · {horizont_label} · {last['date']}</div>
    <div style="font-size:22px;font-weight:bold;color:{farbe};margin-top:4px">{name}</div>
    <div style="font-size:12px;color:#888;margin-top:3px">Elliott Wave · RSI · MACD · EMA 50/200 · {'7-Tage-Prognose' if horizont == 'wöchentlich' else '48h-Prognose'}</div>
  </td></tr>
  <tr><td style="background:{trend_col};padding:12px 16px;color:white;font-weight:bold;font-size:15px">
    {trend_txt} &nbsp; {prog['bull_pct']}% Bull / {prog['bear_pct']}% Bear &nbsp;·&nbsp; {prog['empfehlung']}
  </td></tr>
  <tr><td style="padding:0">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td width="33%" style="background:white;padding:12px;text-align:center;border-right:1px solid #eee">
          <div style="font-size:10px;color:#888">HAUPTSZENARIO ({prog['bull_pct']}%)</div>
          <div style="font-size:16px;font-weight:bold;color:{trend_col}">{prog['target_main']:,.4f}</div>
          <div style="font-size:12px;color:{trend_col}">{pct_main:+.2f}%</div>
        </td>
        <td width="33%" style="background:white;padding:12px;text-align:center;border-right:1px solid #eee">
          <div style="font-size:10px;color:#888">ALTERNATIVSZENARIO ({prog['bear_pct']}%)</div>
          <div style="font-size:16px;font-weight:bold;color:#555">{prog['target_alt']:,.4f}</div>
          <div style="font-size:12px;color:#777">{pct_alt:+.2f}%</div>
        </td>
        <td width="33%" style="background:white;padding:12px;text-align:center">
          <div style="font-size:10px;color:#888">INVALIDIERUNG</div>
          <div style="font-size:16px;font-weight:bold;color:#e74c3c">{prog['inval']:,.4f}</div>
          <div style="font-size:12px;color:#aaa">{einheit}</div>
        </td>
      </tr>
    </table>
  </td></tr>
  <tr><td style="padding:0">
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <tr><td colspan="3" style="background:#2c3e50;color:white;padding:8px 12px;font-size:11px;font-weight:bold;letter-spacing:1px">TECHNISCHE INDIKATOREN</td></tr>
      <tr style="background:white"><td style="padding:8px 12px;color:#555;font-size:13px">Kurs</td><td style="color:{farbe};font-weight:bold;font-size:16px">{px(last['price'])} {einheit}</td><td></td></tr>
      <tr style="background:#f9f9f9"><td style="padding:8px 12px;color:#555;font-size:13px">EMA 50</td><td style="color:#2980b9;font-weight:bold">{px(last['ema50'])}</td><td style="color:{gc(ema50_ok)};font-weight:bold;font-size:12px">{'ÜBER' if ema50_ok else 'UNTER'} EMA50</td></tr>
      <tr style="background:white"><td style="padding:8px 12px;color:#555;font-size:13px">EMA 200</td><td style="color:#c0392b;font-weight:bold">{px(last['ema200'])}</td><td style="color:{gc(ema200_ok)};font-weight:bold;font-size:12px">{'ÜBER' if ema200_ok else 'UNTER'} EMA200</td></tr>
      <tr style="background:#f9f9f9"><td style="padding:8px 12px;color:#555;font-size:13px">RSI (14)</td><td style="color:{rc(rsi_v)};font-weight:bold">{rsi_v}</td><td style="color:{rc(rsi_v)};font-weight:bold;font-size:12px">{rsi_status}</td></tr>
      <tr style="background:white"><td style="padding:8px 12px;color:#555;font-size:13px">MACD</td><td style="color:{tc(last['macd'])};font-weight:bold">{last['macd']}</td><td style="color:{tc(last['macd'])};font-weight:bold;font-size:12px">{'Bullish' if (last['macd'] or 0)>0 else 'Bearish'}</td></tr>
      <tr style="background:#f9f9f9"><td style="padding:8px 12px;color:#555;font-size:13px">Histogramm</td><td style="color:{tc(last['hist'])};font-weight:bold">{last['hist']}</td><td style="color:{tc(last['hist'])};font-weight:bold;font-size:12px">{'Momentum steigt' if (last['hist'] or 0)>0 else 'Momentum fällt'}</td></tr>
      {fund_rows}
    </table>
  </td></tr>
  {charts_row}
  {prognose_row}
  {rest_row}
  <tr><td style="padding:10px;text-align:center;font-size:11px;color:#aaa;background:#f9f9f9">Keine Anlageberatung · Daten: Yahoo Finance / Kraken</td></tr>
</table>
<br>"""

# ── Hauptschleife ──────────────────────────────────────────────────────────────
if st.button("🚀 Analyse starten", type="primary", width="stretch"):
    heute = datetime.date.today().strftime("%d.%m.%Y")
    bar = st.progress(0, text="Starte...")
    n = len(ausgewaehlt)
    mail_html = ""

    # Intervall-Parameter je nach gewähltem Horizont
    horizont_str   = "wöchentlich" if ist_woechentlich else "täglich"
    yahoo_interval = "1wk" if ist_woechentlich else "1d"
    kraken_int     = 10080 if ist_woechentlich else 1440   # Minuten: 7d vs 1d
    fetch_days     = 1500 if ist_woechentlich else 400     # mehr History für Wochenkerzen

    for idx, asset in enumerate(ausgewaehlt):
        name    = asset["name"]
        typ     = asset["typ"]
        einheit = asset["einheit"]
        fortschritt = idx / n

        st.subheader(name, divider="gray")
        bar.progress(fortschritt, text=f"{name}: Kursdaten laden...")

        # Kursdaten
        try:
            if typ == "krypto" and not asset.get("yahoo_krypto"):
                raw = fetch_kraken(asset["pair"], asset["kraken"], days=fetch_days, interval_min=kraken_int)
            elif asset.get("yahoo_krypto"):
                errors = []
                raw = None
                for fn, lbl in [
                    (lambda: fetch_kraken_coin(asset["name"], days=fetch_days, interval_min=kraken_int), "Kraken"),
                    (lambda: resample_weekly(fetch_coincap(asset["name"], days=fetch_days)) if ist_woechentlich else fetch_coincap(asset["name"], days=fetch_days), "CoinCap"),
                    (lambda: fetch_yahoo(asset["symbol"], days=fetch_days, interval=yahoo_interval), "Yahoo"),
                ]:
                    try:
                        raw = fn(); break
                    except Exception as e:
                        errors.append(f"{lbl}: {e}")
                if raw is None:
                    raise Exception(" | ".join(errors))
            else:
                raw = fetch_yahoo(asset["symbol"], days=fetch_days, interval=yahoo_interval)
            data = build(raw)
            last = data[-1]
        except Exception as e:
            st.error(f"Kursdaten-Fehler: {e}"); continue

        # 1. Prognose berechnen
        prog = generate_prognose(data)

        # 2. Fundamentaldaten (nur Aktien)
        fund = {}
        if typ == "aktie" and finnhub_key:
            bar.progress(fortschritt + 0.5/n, text=f"{name}: Fundamentaldaten...")
            fund_raw = fetch_fundamentals(asset["symbol"], finnhub_key)
            err = fund_raw.pop("_error", None) if fund_raw else None
            company_name = fund_raw.pop("_name", None) if fund_raw else None
            if company_name:
                name = f"{company_name} ({asset['symbol']})"
                st.subheader(name)
            fund = fund_raw if (fund_raw and any(v is not None for v in fund_raw.values())) else {}
            if err and not fund:
                st.warning(f"Finnhub: {err}")

        # 3. KI-Analyse
        analyse_text = ""
        ai_modell = ""
        if "Claude" in ai_modus and ai_key:
            bar.progress(fortschritt + 0.75/n, text=f"{name}: Claude analysiert...")
            analyse_text, ai_modell = ai_claude(name, typ, data, fund, prog, ai_key, horizont=horizont_str)
        elif "Gemini" in ai_modus and ai_key:
            bar.progress(fortschritt + 0.75/n, text=f"{name}: Gemini analysiert...")
            analyse_text, ai_modell = ai_gemini(name, typ, data, fund, prog, ai_key, horizont=horizont_str)

        # 4. Karte rendern (iframe für CSS-Isolation vom Streamlit-Theme)
        import streamlit.components.v1 as components
        card_html = render_card(name, typ, einheit, data, prog, fund, analyse_text, ai_modell, horizont=horizont_str)
        full_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{{margin:0;padding:0;background:transparent}}</style></head>
<body>{card_html}</body></html>"""
        height = 5000 if analyse_text else 900
        components.html(full_html, height=height, scrolling=True)

        # HTML für E-Mail sammeln (gleiches Format wie App-Karte)
        mail_html += render_card(name, typ, einheit, data, prog, fund, analyse_text, ai_modell, horizont=horizont_str)

        bar.progress((idx+1)/n, text=f"{name} ✓")
        if idx < n-1:
            time.sleep(0.5)

    bar.progress(1.0, text="Fertig ✓")

    # E-Mail senden
    if send_mail:
        absender = gmail_absender.strip()
        passwort = gmail_passwort.strip().replace(" ", "")  # App-Passwort ggf. ohne Leerzeichen
        empf     = empfaenger.strip()
        if not (absender and passwort and empf):
            st.warning("⚠️ E-Mail: Bitte Absender, App-Passwort und Empfänger ausfüllen.")
        else:
            try:
                msg = MIMEMultipart("alternative")
                horizont_betreff = "Wöchentlich" if ist_woechentlich else "Täglich"
                msg["Subject"] = f"Markt Analyse {horizont_betreff} – {heute}"
                msg["From"]    = absender
                msg["To"]      = empf
                msg.attach(MIMEText(
                    f"<html><body>{mail_html}<p style='color:#aaa;font-size:11px'>Automatisch generiert – keine Anlageberatung</p></body></html>",
                    "html", "utf-8"
                ))
                # Erst Port 465 (SSL), Fallback Port 587 (STARTTLS)
                try:
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
                        s.login(absender, passwort)
                        s.sendmail(absender, empf, msg.as_string())
                except Exception:
                    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
                        s.starttls()
                        s.login(absender, passwort)
                        s.sendmail(absender, empf, msg.as_string())
                st.success(f"✅ E-Mail gesendet an {empf}")
            except Exception as e:
                st.error(f"E-Mail-Fehler: {e}")
                st.info("💡 Tipp: Gmail benötigt ein App-Passwort (nicht dein normales Passwort). Aktiviere zuerst 2-Faktor-Authentifizierung, dann: Google-Konto → Sicherheit → App-Passwörter")

    st.balloons()
