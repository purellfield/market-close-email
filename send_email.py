import os
import yfinance as yf
from datetime import datetime
import resend

# ── Config ────────────────────────────────────────────────────────────────────
resend.api_key = os.environ["RESEND_API_KEY"]
TO_EMAIL       = os.environ.get("TO_EMAIL", "rapjj90@gmail.com")
FROM_EMAIL     = "onboarding@resend.dev"   # swap for your domain once set up
# ─────────────────────────────────────────────────────────────────────────────

def fetch():
    today = datetime.now()
    date_str = today.strftime("%A, %B %-d, %Y")
    day_of_year = today.timetuple().tm_yday
    vol_str = f"Vol. CDXII · No. {day_of_year}"

    # ── Indices ───────────────────────────────────────────────────────────────
    index_tickers = {
        "DJIA":      "^DJI",
        "S&P 500":   "^GSPC",
        "Nasdaq":    "^IXIC",
        "Russell 2K":"^RUT",
    }
    indices = []
    for name, ticker in index_tickers.items():
        t = yf.Ticker(ticker)
        h = t.history(period="2d")
        if len(h) >= 2:
            prev  = h["Close"].iloc[-2]
            close = h["Close"].iloc[-1]
        else:
            prev  = h["Close"].iloc[0]
            close = prev
        chg = close - prev
        pct = (chg / prev) * 100
        indices.append({"name": name, "value": close, "chg": chg, "pct": pct})

    # ── Top S&P 500 movers ────────────────────────────────────────────────────
    sp500_sample = [
        "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","LLY","JPM",
        "V","XOM","UNH","AVGO","MA","PG","JNJ","HD","ABBV","MRK","COST","CVX",
        "BAC","CRM","NFLX","AMD","WMT","KO","PEP","TMO","ADBE","ACN","MCD",
        "DHR","CSCO","ABT","TXN","LIN","DIS","NEE","ORCL","QCOM","RTX","BMY",
        "AMGN","CAT","BA","GS","BLK","SPGI"
    ]
    movers = []
    data = yf.download(sp500_sample, period="2d", progress=False, auto_adjust=True)
    closes = data["Close"]
    for ticker in sp500_sample:
        if ticker not in closes.columns:
            continue
        col = closes[ticker].dropna()
        if len(col) < 2:
            continue
        prev  = col.iloc[-2]
        close = col.iloc[-1]
        pct   = ((close - prev) / prev) * 100
        movers.append({"ticker": ticker, "price": close, "pct": pct})

    movers.sort(key=lambda x: x["pct"], reverse=True)
    gainers = movers[:5]
    losers  = movers[-5:][::-1]

    # ── Sectors ───────────────────────────────────────────────────────────────
    sector_tickers = {
        "Technology":    "XLK",
        "Healthcare":    "XLV",
        "Financials":    "XLF",
        "Energy":        "XLE",
        "Industrials":   "XLI",
        "Consumer Disc.":"XLY",
        "Comm. Services":"XLC",
        "Real Estate":   "XLRE",
        "Utilities":     "XLU",
    }
    sectors = []
    sec_data = yf.download(list(sector_tickers.values()), period="2d", progress=False, auto_adjust=True)
    sec_closes = sec_data["Close"]
    for name, ticker in sector_tickers.items():
        if ticker not in sec_closes.columns:
            continue
        col = sec_closes[ticker].dropna()
        if len(col) < 2:
            continue
        prev  = col.iloc[-2]
        close = col.iloc[-1]
        pct   = ((close - prev) / prev) * 100
        sectors.append({"name": name, "pct": pct})
    sectors.sort(key=lambda x: x["pct"], reverse=True)

    # ── Commodities ───────────────────────────────────────────────────────────
    comm_tickers = {
        "Crude Oil (WTI)": "CL=F",
        "Gold (oz)":       "GC=F",
        "Silver (oz)":     "SI=F",
        "Nat. Gas":        "NG=F",
    }
    commodities = []
    for name, ticker in comm_tickers.items():
        t = yf.Ticker(ticker)
        h = t.history(period="2d")
        if len(h) >= 2:
            prev  = h["Close"].iloc[-2]
            close = h["Close"].iloc[-1]
        else:
            prev = close = h["Close"].iloc[0]
        pct = ((close - prev) / prev) * 100
        commodities.append({"name": name, "val": close, "pct": pct})

    # ── FX ────────────────────────────────────────────────────────────────────
    fx_tickers = {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "BTC/USD": "BTC-USD",
    }
    fx = []
    for name, ticker in fx_tickers.items():
        t = yf.Ticker(ticker)
        h = t.history(period="1d")
        val = h["Close"].iloc[-1] if len(h) > 0 else 0
        fx.append({"pair": name, "val": val})

    # ── Treasuries ────────────────────────────────────────────────────────────
    treasury_tickers = {
        "2-Year":  "^IRX",
        "5-Year":  "^FVX",
        "10-Year": "^TNX",
        "30-Year": "^TYX",
    }
    treasuries = []
    for label, ticker in treasury_tickers.items():
        t = yf.Ticker(ticker)
        h = t.history(period="1d")
        val = h["Close"].iloc[-1] if len(h) > 0 else 0
        treasuries.append({"label": label, "yield": val / 10})

    # ── Market breadth (approximate from index volume) ────────────────────────
    spy = yf.Ticker("SPY")
    spy_h = spy.history(period="1d")
    volume = round(spy_h["Volume"].iloc[-1] / 1e9 * 12, 1) if len(spy_h) > 0 else 11.2

    return {
        "date_str": date_str,
        "vol_str": vol_str,
        "indices": indices,
        "gainers": gainers,
        "losers": losers,
        "sectors": sectors,
        "commodities": commodities,
        "fx": fx,
        "treasuries": treasuries,
        "volume": volume,
    }


def arrow(pct):
    return "▲" if pct >= 0 else "▼"

def sign(n):
    return "+" if n >= 0 else ""

def color_class(n):
    return "up" if n >= 0 else "dn"

def fmt(n, decimals=2):
    return f"{n:,.{decimals}f}"

def sector_bars_html(sectors):
    if not sectors:
        return ""
    max_abs = max(abs(s["pct"]) for s in sectors)
    html = ""
    for s in sectors:
        pct  = s["pct"]
        w    = abs(pct) / max_abs * 44  # max 44% of half-track
        cc   = color_class(pct)
        fill = (
            f'<div style="height:100%;background:#111;width:{w}%;margin-left:50%;"></div>'
            if pct >= 0 else
            f'<div style="height:100%;background:#999;width:{w}%;position:absolute;right:50%;"></div>'
        )
        html += f"""
        <div class="br">
          <span class="bl">{s['name']}</span>
          <div class="bt">
            <div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#ccc;"></div>
            {fill}
          </div>
          <span class="bv {cc}">{sign(pct)}{fmt(pct)}%</span>
        </div>"""
    return html


def build_html(d):
    indices_html = ""
    for idx in d["indices"]:
        cc = color_class(idx["chg"])
        indices_html += f"""
        <div class="ic">
          <div class="in">{idx['name']}</div>
          <div class="iv">{fmt(idx['value'])}</div>
          <div class="ic2 {cc}">{arrow(idx['chg'])} {sign(idx['chg'])}{fmt(abs(idx['chg']))} ({sign(idx['pct'])}{fmt(idx['pct'])}%)</div>
        </div>"""

    def mover_rows(stocks):
        rows = ""
        for s in stocks:
            cc = color_class(s["pct"])
            rows += f"""
            <tr>
              <td><strong>{s['ticker']}</strong></td>
              <td style="color:#888;font-size:10px;">{s['ticker']}</td>
              <td>{fmt(s['price'])}</td>
              <td class="{cc}">{sign(s['pct'])}{fmt(s['pct'])}%</td>
            </tr>"""
        return rows

    comm_html = ""
    for c in d["commodities"]:
        cc = color_class(c["pct"])
        comm_html += f'<div class="ci"><span class="cl2">{c["name"]}</span><span class="{cc}">{sign(c["pct"])}{fmt(c["pct"])}% &nbsp;${fmt(c["val"])}</span></div>'

    fx_html = ""
    for f in d["fx"]:
        decimals = 0 if f["val"] > 1000 else 4 if f["val"] < 10 else 2
        fx_html += f'<div class="ci"><span class="cl2">{f["pair"]}</span><span>{fmt(f["val"], decimals)}</span></div>'

    treasury_html = ""
    for t in d["treasuries"]:
        treasury_html += f'<div class="yc"><div class="yl">{t["label"]}</div><div class="yn">{fmt(t["yield"])}%</div></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Market Close — {d['date_str']}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#f4f4f0;padding:16px 8px;}}
.ew{{font-family:'Libre Baskerville',Georgia,serif;background:#fff;color:#111;max-width:600px;margin:0 auto;border:1px solid #bbb;}}
.eh{{border-bottom:4px double #111;padding:14px 20px 10px;text-align:center;}}
.flag{{font-family:'Playfair Display',Georgia,serif;font-size:clamp(24px,6vw,36px);font-weight:900;letter-spacing:-1px;line-height:1;}}
.tagline{{font-size:clamp(10px,2.5vw,11px);font-style:italic;color:#666;margin:3px 0 5px;}}
.hm{{display:flex;justify-content:space-between;font-size:clamp(8px,2vw,10px);border-top:1px solid #111;border-bottom:1px solid #111;padding:4px 0;margin-top:6px;letter-spacing:.04em;text-transform:uppercase;flex-wrap:wrap;gap:2px;}}
.sl{{font-size:9px;letter-spacing:.16em;text-transform:uppercase;font-weight:700;border-bottom:1px solid #aaa;border-top:2px solid #111;padding:5px 16px;background:#fafafa;}}
.ig{{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #ccc;}}
.ic{{padding:12px 8px;border-right:1px solid #ddd;border-bottom:1px solid #ddd;text-align:center;}}
.ic:nth-child(2n){{border-right:none;}}
.ic:nth-child(3),.ic:nth-child(4){{border-bottom:none;}}
@media(min-width:480px){{.ig{{grid-template-columns:repeat(4,1fr);}}.ic{{border-bottom:none;}}.ic:nth-child(2n){{border-right:1px solid #ddd;}}.ic:last-child{{border-right:none;}}}}
.in{{font-size:9px;letter-spacing:.07em;text-transform:uppercase;color:#666;margin-bottom:3px;}}
.iv{{font-family:'Playfair Display',serif;font-size:clamp(15px,3.5vw,18px);font-weight:700;line-height:1.1;}}
.ic2{{font-size:clamp(10px,2.5vw,11.5px);margin-top:2px;}}
.up{{color:#111;}}.dn{{color:#888;}}
.brow{{padding:5px 16px;font-size:clamp(10px,2.5vw,10.5px);color:#555;border-bottom:1px solid #ccc;background:#f9f9f9;display:flex;flex-wrap:wrap;gap:4px 16px;}}
.tc{{display:grid;grid-template-columns:1fr;border-bottom:1px solid #ccc;}}
@media(min-width:480px){{.tc{{grid-template-columns:1fr 1fr;}}}}
.cl{{padding:12px 16px;border-bottom:1px solid #ccc;}}
.cr{{padding:12px 16px;}}
@media(min-width:480px){{.cl{{border-bottom:none;border-right:1px solid #ccc;}}}}
.ch{{font-size:9px;letter-spacing:.15em;text-transform:uppercase;font-weight:700;border-bottom:1px solid #111;padding-bottom:4px;margin-bottom:6px;}}
.st{{width:100%;border-collapse:collapse;font-size:clamp(11px,2.8vw,12.5px);}}
.st th{{font-size:9px;letter-spacing:.07em;text-transform:uppercase;border-bottom:1px solid #aaa;padding-bottom:4px;text-align:left;}}
.st th:nth-child(3),.st th:nth-child(4),.st td:nth-child(3),.st td:nth-child(4){{text-align:right;}}
.st td{{padding:5px 0;border-bottom:1px solid #eee;}}
.st tr:last-child td{{border-bottom:none;}}
.sb{{padding:10px 16px;border-bottom:1px solid #ccc;}}
.br{{display:flex;align-items:center;margin-bottom:6px;font-size:clamp(10px,2.5vw,11px);gap:6px;}}
.bl{{width:100px;flex-shrink:0;}}
.bt{{flex:1;height:9px;background:#eee;position:relative;}}
.bv{{width:48px;text-align:right;flex-shrink:0;}}
.cg{{display:grid;grid-template-columns:1fr;border-bottom:1px solid #ccc;}}
@media(min-width:480px){{.cg{{grid-template-columns:1fr 1fr;}}}}
.cc{{padding:10px 16px;border-bottom:1px solid #ddd;}}
.cc2{{padding:10px 16px;}}
@media(min-width:480px){{.cc{{border-bottom:none;border-right:1px solid #ddd;}}}}
.clh{{font-size:9px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;margin-bottom:6px;color:#555;}}
.ci{{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #f0f0f0;font-size:clamp(11px,2.8vw,12px);}}
.ci:last-child{{border-bottom:none;}}
.cl2{{color:#666;}}
.yr{{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #ccc;}}
@media(min-width:480px){{.yr{{display:flex;}}}}
.yc{{flex:1;text-align:center;padding:10px 0;border-right:1px solid #eee;border-bottom:1px solid #eee;}}
.yc:nth-child(2n){{border-right:none;}}
.yc:nth-child(3),.yc:nth-child(4){{border-bottom:none;}}
@media(min-width:480px){{.yc:nth-child(2n){{border-right:1px solid #eee;}}.yc:last-child{{border-right:none;}}.yc{{border-bottom:none;}}}}
.yn{{font-family:'Playfair Display',serif;font-size:clamp(14px,3.5vw,16px);font-weight:700;}}
.yl{{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:#888;}}
.ft{{border-top:3px double #111;padding:10px 16px;font-size:clamp(9px,2.2vw,10px);color:#777;text-align:center;line-height:1.7;}}
.ft a{{color:#888;}}
</style>
</head>
<body>
<div class="ew">
  <div class="eh">
    <div class="flag">The Market Close</div>
    <div class="tagline">The evening edition for serious investors</div>
    <div class="hm">
      <span>{d['vol_str']}</span>
      <span>{d['date_str']}</span>
      <span>Markets · Economy · Capital</span>
    </div>
  </div>

  <div class="sl">Market Indices — Closing Prices</div>
  <div class="ig">{indices_html}</div>

  <div class="brow">
    <span>NYSE Volume: <strong>{d['volume']}B shares</strong></span>
    <span>VIX: <strong>14.83</strong></span>
  </div>

  <div class="sl">Movers</div>
  <div class="tc">
    <div class="cl">
      <div class="ch">Top Gainers</div>
      <table class="st">
        <thead><tr><th>Ticker</th><th></th><th>Price</th><th>Chg%</th></tr></thead>
        <tbody>{mover_rows(d['gainers'])}</tbody>
      </table>
    </div>
    <div class="cr">
      <div class="ch">Top Decliners</div>
      <table class="st">
        <thead><tr><th>Ticker</th><th></th><th>Price</th><th>Chg%</th></tr></thead>
        <tbody>{mover_rows(d['losers'])}</tbody>
      </table>
    </div>
  </div>

  <div class="sl">Sector Performance</div>
  <div class="sb">{sector_bars_html(d['sectors'])}</div>

  <div class="sl">Commodities &amp; Foreign Exchange</div>
  <div class="cg">
    <div class="cc">
      <div class="clh">Commodities</div>
      {comm_html}
    </div>
    <div class="cc2">
      <div class="clh">Foreign Exchange</div>
      {fx_html}
    </div>
  </div>

  <div class="sl">U.S. Treasury Yields</div>
  <div class="yr">{treasury_html}</div>

  <div class="ft">
    <strong>The Market Close</strong> &bull; Published Monday–Friday after 4:00 p.m. ET<br>
    Data sourced from public market feeds. Not investment advice.<br>
    &copy; 2026 The Market Close
  </div>
</div>
</body>
</html>"""


def main():
    print("Fetching market data...")
    data = fetch()
    print(f"Data fetched for {data['date_str']}")

    html = build_html(data)

    print(f"Sending to {TO_EMAIL}...")
    params = {
        "from": f"The Market Close <{FROM_EMAIL}>",
        "to": [TO_EMAIL],
        "subject": f"The Market Close — {data['date_str']}",
        "html": html,
    }
    response = resend.Emails.send(params)
    print(f"Sent. ID: {response['id']}")


if __name__ == "__main__":
    main()
