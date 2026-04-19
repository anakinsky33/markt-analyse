#!/usr/bin/env python3
import streamlit as st
import os, json, datetime, urllib.request, urllib.parse, time, smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    if st.checkbox("S&P 500 (^GSPC)", value=True, key="sp500"):
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
            if st.checkbox(a["name"], value=True, key=a["symbol"]):
                ausgewaehlt.append(a)

    st.divider()

    # API Keys
    st.subheader("🔑 API Keys")
    finnhub_key = st.text_input(
        "Finnhub (Fundamentaldaten)",
        value=get_secret("FINNHUB_API_KEY"),
        type="password",
        placeholder="finnhub.io → kostenlos",
    )

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
    if send_mail:
        gmail_absender = st.text_input("Absender Gmail",  value=get_secret("GMAIL_ABSENDER"))
        gmail_passwort = st.text_input("App-Passwort",    value=get_secret("GMAIL_APP_PASSWORT"), type="password")
        empfaenger     = st.text_input("Empfänger",       value=get_secret("EMPFAENGER"))
    else:
        gmail_absender = gmail_passwort = empfaenger = ""

# ── Hauptbereich Header ────────────────────────────────────────────────────────
st.title("📊 Markt Analyse")
st.caption("Aktien · Krypto · Edelmetalle  |  Elliott Wave · RSI · MACD · EMA · KI-Analyse · 48h-Prognose")

if not ausgewaehlt:
    st.warning("Bitte mindestens ein Asset auswählen.")
    st.stop()

# ── Datenabruf ─────────────────────────────────────────────────────────────────
def fetch_yahoo(symbol, days=400):
    now   = datetime.datetime.now(datetime.timezone.utc)
    end   = int(now.timestamp())
    start = int((now - datetime.timedelta(days=days)).timestamp())
    url   = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
             f"?interval=1d&period1={start}&period2={end}")
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    result = data["chart"]["result"][0]
    return [{"date": datetime.date.fromtimestamp(ts).isoformat(), "close": round(float(c), 4)}
            for ts, c in zip(result["timestamp"], result["indicators"]["quote"][0]["close"])
            if c is not None and c > 0]

def fetch_kraken(pair, kraken_key, days=720):
    since = int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).timestamp())
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440&since={since}"
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
def _build_prompt(name, typ, data, fund, prog):
    last = data[-1]
    def fp(v): return f"{v:.4f}" if v else "—"
    def px(v): return f"{v:,.4f}" if v else "—"
    def pct(v): return f"{v*100:.1f}%" if v else "—"
    f = fund or {}

    # Letzte 30 Tage als Kontext
    history = "\n".join(
        f"  {d['date']}: {px(d['price'])} | RSI:{d['rsi']} | MACD:{d['macd']} | Hist:{d['hist']}"
        for d in data[-30:]
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
        "aktie":  f"Du bist ein erfahrener Aktienanalyst mit Expertise in Elliott-Wellen, RSI, MACD und EMAs. Analysiere {name} präzise und meinungsstark auf Deutsch. Nenne immer konkrete Kurslevels.",
        "krypto": f"Du bist ein erfahrener Kryptoanalyst mit Expertise in Elliott-Wellen, RSI, MACD und EMAs. Analysiere {name}/USD präzise und meinungsstark auf Deutsch. Nenne immer konkrete Kurslevels in USD.",
        "metall": f"Du bist ein erfahrener Edelmetall-Analyst mit Expertise in Elliott-Wellen, RSI, MACD und EMAs. Analysiere {name} präzise und meinungsstark auf Deutsch. Nenne immer konkrete Preislevels in USD pro Unze.",
    }
    system = system_map.get(typ, f"Du bist ein erfahrener Finanzanalyst. Analysiere {name} auf Deutsch.")
    trend = "BULLISCH" if prog["main_bull"] else "BÄRISCH"
    sektion5 = (
        "## 5. Fundamentale Bewertung\nBewerte KGV, Wachstum, Margen und Verschuldung im Branchenvergleich."
        if typ == "aktie" else
        "## 5. Marktsentiment & Makrofaktoren\nWas treibt den Markt aktuell? Welche externen Faktoren sind relevant?"
    )

    return f"""{system}

AKTUELL ({last['date']}):
- Kurs:    {px(last['price'])}
- EMA 50:  {px(last['ema50'])}
- EMA 200: {px(last['ema200'])}
- RSI(14): {fp(last['rsi'])}
- MACD:    {fp(last['macd'])} | Signal: {fp(last['signal'])} | Histogramm: {fp(last['hist'])}
- Regelbasierter Trend: {trend} ({prog['bull_pct']}% Bull / {prog['bear_pct']}% Bear)
{fund_block}

LETZTE 30 TAGE:
{history}

Erstelle eine vollständige technische Analyse:

## 1. Elliott-Wellen-Analyse
Aktive Welle? Impuls oder Korrektur? Position im Zyklus?

## 2. EMA-Trendstruktur
Preis vs. EMA50 vs. EMA200. Golden Cross / Death Cross? Trendstärke?

## 3. RSI-Analyse
Momentum, überkauft/überverkauft, Divergenzen?

## 4. MACD-Analyse
Crossover, Histogramm-Richtung, Momentum-Veränderung?

{sektion5}

## 6. Gesamtbild & Schlüsselniveaus
Übergeordneter Bias + konkrete Support- und Resistance-Zonen.

## 7. 2-Tages-Prognose (48h)
- HAUPTSZENARIO (XX% Wahrscheinlichkeit): Konkreter Kursverlauf mit Zielkurs und % Veränderung.
- ALTERNATIVSZENARIO (XX% Wahrscheinlichkeit): Gegenszenario mit Kursziel.
- ENTSCHEIDENDE MARKEN: Welche Levels bestimmen das Szenario?
- INVALIDIERUNGSLEVEL: Ab welchem Kurs wird das Hauptszenario ungültig?
- HANDLUNGSEMPFEHLUNG: Klar und direkt."""

def ai_claude(name, typ, data, fund, prog, key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2500,
            messages=[{"role":"user","content":_build_prompt(name,typ,data,fund,prog)}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"⚠️ Claude-Fehler: {e}"

def ai_gemini(name, typ, data, fund, prog, key):
    try:
        body = json.dumps({"contents":[{"parts":[{"text":_build_prompt(name,typ,data,fund,prog)}]}]}).encode()
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        req  = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            resp = json.loads(r.read())
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"⚠️ Gemini-Fehler: {e}"

# ── Darstellung (Email-Stil) ───────────────────────────────────────────────────
ASSET_FARBEN = {"aktie": "#1a73e8", "krypto": "#f7931a", "metall": "#FFD700"}

def render_card(name, typ, einheit, last, prog, fund, analyse_text):
    import html as hl
    farbe = ASSET_FARBEN.get(typ, "#888")

    def px(v):  return f"{v:,.4f}" if v else "—"
    def rc(v):
        if not v: return "#888"
        return "#e74c3c" if v > 70 else ("#27ae60" if v < 30 else "#f39c12")
    def tc(v):  return "#27ae60" if (v or 0) > 0 else "#e74c3c"
    def gc(ok): return "#27ae60" if ok else "#e74c3c"

    ema50_ok  = (last["price"] or 0) > (last["ema50"]  or 0)
    ema200_ok = (last["price"] or 0) > (last["ema200"] or 0)
    rsi_v     = last["rsi"] or 0
    rsi_status = "Überkauft" if rsi_v > 70 else ("Überverkauft" if rsi_v < 30 else "Neutral")

    def row(bg, label, value, vc, status, sc):
        return (f'<tr style="border-bottom:1px solid #eee;background:{bg}">'
                f'<td style="padding:10px 15px;color:#555;font-size:13px">{label}</td>'
                f'<td style="padding:10px 15px;font-weight:bold;color:{vc}">{value}</td>'
                f'<td style="padding:10px 15px;font-size:12px;font-weight:bold;color:{sc}">{status}</td></tr>')

    # Prognose-Zeilen
    p = prog["current"]
    pct_main = (prog["target_main"] - p) / p * 100
    pct_alt  = (prog["target_alt"]  - p) / p * 100
    trend_col = "#27ae60" if prog["main_bull"] else "#e74c3c"
    trend_txt = "📈 BULLISCH" if prog["main_bull"] else "📉 BÄRISCH"

    # Fundamentaldaten-Block
    fund_html = ""
    if typ == "aktie" and fund:
        def fp(v): return f"{v:.2f}" if v is not None else "—"
        def pct(v): return f"{v*100:.1f} %" if v is not None else "—"
        def mc(v): return (f"${v/1e12:.2f} T" if v >= 1e12 else f"${v/1e9:.2f} B") if v else "—"
        fund_html = f"""
  <div style="background:white;border-radius:8px;margin-bottom:16px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
    <div style="background:#2c3e50;color:white;padding:9px 15px;font-size:11px;font-weight:bold;letter-spacing:1px">FUNDAMENTALDATEN</div>
    <table style="width:100%;border-collapse:collapse">
      {row("white",   "Marktkapitalisierung", mc(fund.get("marketCap")),     "#333","","") }
      {row("#fafafa", "KGV (Trailing)",        fp(fund.get("trailingPE")),    "#333","","") }
      {row("white",   "KGV (Forward)",         fp(fund.get("forwardPE")),     "#333","","") }
      {row("#fafafa", "EPS",                   fp(fund.get("trailingEps")),   "#333","","") }
      {row("white",   "Dividendenrendite",     pct(fund.get("dividendYield")),"#333","","") }
      {row("#fafafa", "Gewinnmarge",           pct(fund.get("profitMargins")),"#333","","") }
      {row("white",   "ROE",                   pct(fund.get("returnOnEquity")),"#333","","") }
      {row("#fafafa", "52W-Hoch / Tief",       fp(fund.get("week52High")) + " / " + fp(fund.get("week52Low")), "#333","","") }
    </table>
  </div>"""

    # Analyse-Text formatieren
    analyse_html = ""
    if analyse_text:
        for line in analyse_text.split("\n"):
            if line.startswith("## "):
                sec = line[3:]
                is_p = "7." in sec or "Prognose" in sec or "48h" in sec
                bc = "#e74c3c" if is_p else farbe
                tc2 = "#c0392b" if is_p else "#2c3e50"
                analyse_html += (f'<h3 style="color:{tc2};border-bottom:3px solid {bc};'
                                 f'padding:8px 0 5px 0;margin-top:24px;font-size:15px">{hl.escape(sec)}</h3>')
            elif any(line.startswith(f"- {k}") for k in ["HAUPTSZENARIO", "ALTERNATIVSZENARIO"]):
                analyse_html += f'<p style="margin:7px 0;line-height:1.8;font-weight:bold;color:#e74c3c">{hl.escape(line)}</p>'
            elif any(line.startswith(f"- {k}") for k in ["ENTSCHEIDENDE", "INVALIDIERUNG", "HANDLUNG"]):
                analyse_html += f'<p style="margin:7px 0;line-height:1.8;font-weight:bold;color:#f39c12">{hl.escape(line)}</p>'
            elif line.startswith("**") and line.endswith("**"):
                analyse_html += f'<p style="margin:4px 0;line-height:1.7"><strong>{hl.escape(line.strip("*"))}</strong></p>'
            elif line.strip():
                analyse_html += f'<p style="margin:4px 0;line-height:1.7">{hl.escape(line)}</p>'

    kat_label = {"aktie": "AKTIEN ANALYSE", "krypto": "KRYPTO ANALYSE", "metall": "EDELMETALL ANALYSE"}.get(typ, "ANALYSE")

    html = f"""
<div style="font-family:Arial,sans-serif;background:#f0f2f6;padding:16px;border-radius:10px;margin-bottom:8px">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;padding:18px 20px;border-radius:8px;margin-bottom:14px;border-left:5px solid {farbe}">
    <div style="font-size:10px;letter-spacing:2px;opacity:0.55;text-transform:uppercase">{kat_label} · DAILY · {last['date']}</div>
    <div style="font-size:22px;font-weight:bold;margin-top:4px;color:{farbe}">{hl.escape(name)}</div>
    <div style="font-size:12px;opacity:0.65;margin-top:3px">Elliott Wave · RSI · MACD · EMA 50/200 · 48h-Prognose</div>
  </div>

  <!-- Prognose-Banner -->
  <div style="background:{trend_col};color:white;padding:12px 16px;border-radius:8px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:16px;font-weight:bold">{trend_txt} &nbsp; {prog['bull_pct']}% Bull / {prog['bear_pct']}% Bear</span>
    <span style="font-size:13px;opacity:0.9">{prog['empfehlung']}</span>
  </div>

  <!-- Kursziele -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px">
    <div style="background:white;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
      <div style="font-size:10px;color:#888;margin-bottom:4px">HAUPTSZENARIO ({prog['bull_pct']}%)</div>
      <div style="font-size:16px;font-weight:bold;color:{trend_col}">{prog['target_main']:,.4f}</div>
      <div style="font-size:12px;color:{trend_col}">{pct_main:+.2f}%</div>
    </div>
    <div style="background:white;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
      <div style="font-size:10px;color:#888;margin-bottom:4px">ALTERNATIVSZENARIO ({prog['bear_pct']}%)</div>
      <div style="font-size:16px;font-weight:bold;color:#555">{prog['target_alt']:,.4f}</div>
      <div style="font-size:12px;color:#777">{pct_alt:+.2f}%</div>
    </div>
    <div style="background:white;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
      <div style="font-size:10px;color:#888;margin-bottom:4px">INVALIDIERUNG</div>
      <div style="font-size:16px;font-weight:bold;color:#e74c3c">{prog['inval']:,.4f}</div>
      <div style="font-size:12px;color:#aaa">{einheit}</div>
    </div>
  </div>

  <!-- Indikatoren -->
  <div style="background:white;border-radius:8px;margin-bottom:14px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
    <div style="background:#2c3e50;color:white;padding:9px 15px;font-size:11px;font-weight:bold;letter-spacing:1px">TECHNISCHE INDIKATOREN</div>
    <table style="width:100%;border-collapse:collapse">
      {row("white",   "Kurs", f'<span style="font-size:17px">{px(last["price"])} {einheit}</span>', farbe, "", "")}
      {row("#fafafa", "EMA 50",     px(last["ema50"]),  "#2980b9", "Preis ÜBER EMA50"   if ema50_ok  else "Preis UNTER EMA50",   gc(ema50_ok))}
      {row("white",   "EMA 200",    px(last["ema200"]), "#c0392b", "Preis ÜBER EMA200"  if ema200_ok else "Preis UNTER EMA200",  gc(ema200_ok))}
      {row("#fafafa", "RSI (14)",   str(rsi_v),         rc(rsi_v), rsi_status, rc(rsi_v))}
      {row("white",   "MACD",       str(last["macd"]),  tc(last["macd"]), "Bullish" if (last["macd"] or 0)>0 else "Bearish", tc(last["macd"]))}
      {row("#fafafa", "Histogramm", str(last["hist"]),  tc(last["hist"]), "Momentum steigt" if (last["hist"] or 0)>0 else "Momentum fällt", tc(last["hist"]))}
    </table>
  </div>

  {fund_html}

  <!-- KI-Analyse -->
  {"" if not analyse_text else f'''
  <div style="background:white;border-radius:8px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
    <div style="font-size:10px;color:#888;letter-spacing:1px;margin-bottom:12px">KI-ANALYSE</div>
    ''' + analyse_html + '''
  </div>'''}

  <div style="text-align:center;margin-top:12px;font-size:11px;color:#aaa">Keine Anlageberatung · Daten: Yahoo Finance / Kraken</div>
</div>"""

    return html

# ── Hauptschleife ──────────────────────────────────────────────────────────────
if st.button("🚀 Analyse starten", type="primary", width="stretch"):
    heute = datetime.date.today().strftime("%d.%m.%Y")
    bar = st.progress(0, text="Starte...")
    n = len(ausgewaehlt)
    mail_html = ""

    for idx, asset in enumerate(ausgewaehlt):
        name    = asset["name"]
        typ     = asset["typ"]
        einheit = asset["einheit"]
        fortschritt = idx / n

        st.subheader(name, divider="gray")
        bar.progress(fortschritt, text=f"{name}: Kursdaten laden...")

        # Kursdaten
        try:
            if typ == "krypto":
                raw = fetch_kraken(asset["pair"], asset["kraken"])
            else:
                raw = fetch_yahoo(asset["symbol"])
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
        if "Claude" in ai_modus and ai_key:
            bar.progress(fortschritt + 0.75/n, text=f"{name}: Claude analysiert...")
            analyse_text = ai_claude(name, typ, data, fund, prog, ai_key)
        elif "Gemini" in ai_modus and ai_key:
            bar.progress(fortschritt + 0.75/n, text=f"{name}: Gemini analysiert...")
            analyse_text = ai_gemini(name, typ, data, fund, prog, ai_key)

        # 4. Karte rendern
        card_html = render_card(name, typ, einheit, last, prog, fund, analyse_text)
        st.markdown(card_html, unsafe_allow_html=True)

        # HTML für E-Mail sammeln
        mail_html += card_html

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
                msg["Subject"] = f"Markt Analyse – {heute}"
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
