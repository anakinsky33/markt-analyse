#!/usr/bin/env python3
import streamlit as st
import os, json, datetime, urllib.request, time, smtplib
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
        "Weitere Aktien (Ticker, kommagetrennt)",
        placeholder="z.B. NVDA, AAPL, MSFT, SAP",
        help="Yahoo Finance Ticker-Symbol eingeben, z.B. NVDA, AAPL, SAP.DE",
    )
    for ticker in [t.strip().upper() for t in aktien_eingabe.split(",") if t.strip()]:
        ausgewaehlt.append({"name": ticker, "symbol": ticker, "typ": "aktie", "einheit": "USD"})

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
def _build_prompt(name, typ, last, fund, prog):
    def fp(v): return f"{v:.4f}" if v else "—"
    def pct(v): return f"{v*100:.1f}%" if v else "—"
    f = fund or {}
    fund_block = ""
    if typ == "aktie" and f:
        fund_block = f"""
FUNDAMENTALDATEN:
- Marktkapitalisierung: {f.get('marketCap') and f'${f["marketCap"]/1e9:.1f}B' or '—'}
- KGV (TTM): {fp(f.get('trailingPE'))} | EPS: {fp(f.get('trailingEps'))}
- Gewinnmarge: {pct(f.get('profitMargins'))} | ROE: {pct(f.get('returnOnEquity'))}
- Dividendenrendite: {pct(f.get('dividendYield'))}
- 52W-Hoch: {fp(f.get('week52High'))} | 52W-Tief: {fp(f.get('week52Low'))}"""

    asset_kontext = {
        "aktie":  "Aktienmarkt mit Fokus auf Unternehmensperformance und Marktumfeld",
        "krypto": "Kryptomarkt mit Fokus auf On-Chain-Dynamik, Marktsentiment und Makrofaktoren",
        "metall": "Edelmetallmarkt mit Fokus auf Inflationsschutz, USD-Stärke und geopolitische Risiken",
    }.get(typ, "Finanzmarkt")

    return f"""Du bist ein erfahrener Analyst für {asset_kontext}. Analysiere {name} präzise auf Deutsch.

TECHNISCHE DATEN (aktuell):
- Kurs: {last['price']:.4f} | EMA50: {fp(last['ema50'])} | EMA200: {fp(last['ema200'])}
- RSI(14): {fp(last['rsi'])} | MACD: {fp(last['macd'])} | Signal: {fp(last['signal'])} | Hist: {fp(last['hist'])}
- Trend: {'BULLISCH' if prog['main_bull'] else 'BÄRISCH'} ({prog['bull_pct']}% Bull / {prog['bear_pct']}% Bear)
- Bullische Signale: {', '.join(prog['signals_bull']) or '—'}
- Bärische Signale:  {', '.join(prog['signals_bear']) or '—'}
{fund_block}

Schreibe eine strukturierte Analyse:
## 1. Marktlage & Trendstruktur
## 2. Elliott-Wellen-Einschätzung
## 3. Technische Indikatoren (EMA, RSI, MACD)
{"## 4. Fundamentale Bewertung" if typ == "aktie" else "## 4. Marktsentiment & Besonderheiten"}
## 5. 48h-Prognose & Handlungsempfehlung
- HAUPTSZENARIO (XX%): Kursziel mit % Veränderung
- ALTERNATIVSZENARIO (XX%): Gegenszenario
- INVALIDIERUNGSLEVEL: ab welchem Kurs ungültig

Antworte professionell, konkret, auf Deutsch."""

def ai_claude(name, typ, last, fund, prog, key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            messages=[{"role":"user","content":_build_prompt(name,typ,last,fund,prog)}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"⚠️ Claude-Fehler: {e}"

def ai_gemini(name, typ, last, fund, prog, key):
    try:
        body = json.dumps({"contents":[{"parts":[{"text":_build_prompt(name,typ,last,fund,prog)}]}]}).encode()
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        req  = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"⚠️ Gemini-Fehler: {e}"

# ── Anzeige-Funktionen ─────────────────────────────────────────────────────────
def show_prognose(prog, einheit):
    farbe = "green" if prog["main_bull"] else "red"
    richtung = "📈 BULLISCH" if prog["main_bull"] else "📉 BÄRISCH"
    p = prog["current"]
    st.subheader(f"🕐 48h-Prognose — :{farbe}[{richtung}]")
    c1,c2,c3 = st.columns(3)
    with c1:
        st.metric(f"Hauptszenario ({prog['bull_pct']}%)",
                  f"{prog['target_main']:,.4f} {einheit}",
                  f"{(prog['target_main']-p)/p*100:+.2f}%")
    with c2:
        st.metric(f"Alternativszenario ({prog['bear_pct']}%)",
                  f"{prog['target_alt']:,.4f} {einheit}",
                  f"{(prog['target_alt']-p)/p*100:+.2f}%")
    with c3:
        st.metric("Invalidierungslevel", f"{prog['inval']:,.4f} {einheit}")
    st.info(f"**Handlungsempfehlung:** {prog['empfehlung']}")
    with st.expander("📊 Signal-Details"):
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("**🟢 Bullische Signale**")
            for s in prog["signals_bull"]: st.markdown(f"- {s}")
        with c2:
            st.markdown("**🔴 Bärische Signale**")
            for s in prog["signals_bear"]: st.markdown(f"- {s}")

def fmt_fund_df(fund):
    def fp(v): return f"{v:.2f}" if v is not None else "—"
    def pct(v): return f"{v*100:.1f} %" if v is not None else "—"
    def mc(v): return (f"${v/1e12:.2f} T" if v>=1e12 else f"${v/1e9:.2f} B") if v else "—"
    return pd.DataFrame([
        ("Marktkapitalisierung", mc(fund.get("marketCap"))),
        ("KGV Trailing",         fp(fund.get("trailingPE"))),
        ("KGV Forward",          fp(fund.get("forwardPE"))),
        ("Kurs / Buchwert",      fp(fund.get("priceToBook"))),
        ("EPS (Trailing)",       fp(fund.get("trailingEps"))),
        ("Dividendenrendite",    pct(fund.get("dividendYield"))),
        ("Umsatzwachstum",       pct(fund.get("revenueGrowth"))),
        ("Gewinnwachstum",       pct(fund.get("earningsGrowth"))),
        ("Gewinnmarge",          pct(fund.get("profitMargins"))),
        ("Eigenkapitalrendite",  pct(fund.get("returnOnEquity"))),
        ("Verschuldungsgrad",    fp(fund.get("debtToEquity"))),
        ("52W-Hoch / Tief",      f"{fp(fund.get('week52High'))} / {fp(fund.get('week52Low'))}"),
    ], columns=["Kennzahl","Wert"])

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

        # 1. Prognose (oben)
        prog = generate_prognose(data)
        show_prognose(prog, einheit)
        st.markdown("---")

        # 2. Indikatoren + Fundamentaldaten
        bar.progress(fortschritt + 0.5/n, text=f"{name}: Indikatoren...")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Aktueller Kurs", f"{last['price']:,.4f} {einheit}")
            ema50_ok  = last["price"] > (last["ema50"]  or 0)
            ema200_ok = last["price"] > (last["ema200"] or 0)
            rsi_val   = last["rsi"] or 0
            st.dataframe(pd.DataFrame([
                ["EMA 50",     f"{last['ema50']:,.4f}" if last['ema50'] else "—",
                 "🟢 darüber" if ema50_ok  else "🔴 darunter"],
                ["EMA 200",    f"{last['ema200']:,.4f}" if last['ema200'] else "—",
                 "🟢 darüber" if ema200_ok else "🔴 darunter"],
                ["RSI (14)",   str(rsi_val),
                 "🔴 Überkauft" if rsi_val>70 else ("🟢 Überverkauft" if rsi_val<30 else "🟡 Neutral")],
                ["MACD",       str(last["macd"]),
                 "🟢 Bullish" if (last["macd"] or 0)>0 else "🔴 Bearish"],
                ["Histogramm", str(last["hist"]),
                 "🟢 steigt"  if (last["hist"] or 0)>0 else "🔴 fällt"],
            ], columns=["Indikator","Wert","Status"]), hide_index=True, width="stretch")

        # Fundamentaldaten (nur Aktien)
        fund = {}
        with col2:
            if typ == "aktie" and finnhub_key:
                bar.progress(fortschritt + 0.6/n, text=f"{name}: Fundamentaldaten...")
                fund_raw = fetch_fundamentals(asset["symbol"], finnhub_key)
                err = fund_raw.pop("_error", None) if fund_raw else None
                # Firmenname übernehmen falls vorhanden
                company_name = fund_raw.pop("_name", None) if fund_raw else None
                if company_name:
                    name = f"{company_name} ({asset['symbol']})"
                    st.subheader(name)  # Überschrift aktualisieren
                fund = fund_raw if (fund_raw and any(v is not None for v in fund_raw.values())) else {}
                if fund:
                    st.markdown("**Fundamentaldaten**")
                    st.dataframe(fmt_fund_df(fund), hide_index=True, width="stretch")
                elif err:
                    st.warning(f"Finnhub: {err}")
                else:
                    st.info("Keine Fundamentaldaten verfügbar")
            elif typ == "krypto":
                st.info("ℹ️ Fundamentaldaten nicht anwendbar für Krypto")
            elif typ == "metall":
                st.info("ℹ️ Fundamentaldaten nicht anwendbar für Edelmetalle")

        # 3. KI-Analyse
        analyse_text = ""
        if "Claude" in ai_modus and ai_key:
            bar.progress(fortschritt + 0.75/n, text=f"{name}: Claude analysiert...")
            analyse_text = ai_claude(name, typ, last, fund, prog, ai_key)
            st.markdown("### 🔵 KI-Analyse (Claude)")
            st.markdown(analyse_text)
        elif "Gemini" in ai_modus and ai_key:
            bar.progress(fortschritt + 0.75/n, text=f"{name}: Gemini analysiert...")
            analyse_text = ai_gemini(name, typ, last, fund, prog, ai_key)
            st.markdown("### 🟢 KI-Analyse (Gemini)")
            st.markdown(analyse_text)

        # HTML für E-Mail sammeln
        farbe_hex = {"aktie":"#1a73e8","krypto":"#f7931a","metall":"#FFD700"}.get(typ,"#888")
        mail_html += f"""
<div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto 30px auto;background:#f8f9fa;padding:20px;border-radius:8px;border-left:5px solid {farbe_hex}">
  <h2 style="margin:0 0 8px 0;color:{farbe_hex}">{name}</h2>
  <p style="margin:4px 0">Kurs: <strong>{last['price']:,.4f} {einheit}</strong> &nbsp;|&nbsp;
     RSI: {rsi_val} &nbsp;|&nbsp; {'📈 BULLISCH' if prog['main_bull'] else '📉 BÄRISCH'} ({prog['bull_pct']}%)</p>
  <p style="margin:4px 0">Hauptszenario: <strong>{prog['target_main']:,.4f}</strong>
     ({(prog['target_main']-prog['current'])/prog['current']*100:+.2f}%)</p>
  <p style="margin:4px 0">Empfehlung: <strong>{prog['empfehlung']}</strong></p>
  {"<hr/><pre style='font-size:12px;white-space:pre-wrap'>" + analyse_text + "</pre>" if analyse_text else ""}
</div>
<hr style="border:none;border-top:2px solid #ddd;margin:10px 0 20px 0">"""

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
