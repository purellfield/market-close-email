import os
import yfinance as yf
from datetime import datetime, timedelta
import requests
import resend

# ── Config ────────────────────────────────────────────────────────────────────
resend.api_key = os.environ["RESEND_API_KEY"]
TO_EMAIL   = os.environ.get("TO_EMAIL", "rapjj90@gmail.com")
FROM_EMAIL = "onboarding@resend.dev"   # swap for your domain once set up
# ─────────────────────────────────────────────────────────────────────────────

BASEBALL_TEAMS = ["LAD", "NYY", "ATL"]


def fetch():
    today    = datetime.now()
    date_str = today.strftime("%A, %B %-d, %Y")
    vol_str  = f"Vol. CDXII · No. {today.timetuple().tm_yday}"

    # ── Indices ───────────────────────────────────────────────────────────────
    index_tickers = {
        "DJIA":       "^DJI",
        "S&P 500":    "^GSPC",
        "Nasdaq":     "^IXIC",
        "Russell 2K": "^RUT",
    }
    indices = []
    for name, ticker in index_tickers.items():
        h = yf.Ticker(ticker).history(period="2d")
        if len(h) >= 2:
            prev, close = h["Close"].iloc[-2], h["Close"].iloc[-1]
        else:
            prev = close = h["Close"].iloc[0]
        chg = close - prev
        pct = (chg / prev) * 100
        indices.append({"name": name, "value": close, "chg": chg, "pct": pct})

    # ── VIX ───────────────────────────────────────────────────────────────────
    vix_h = yf.Ticker("^VIX").history(period="1d")
    vix   = vix_h["Close"].iloc[-1] if len(vix_h) > 0 else 0

    # ── Sectors ───────────────────────────────────────────────────────────────
    sector_tickers = {
        "Technology":    "XLK", "Healthcare":    "XLV", "Financials":    "XLF",
        "Energy":        "XLE", "Industrials":   "XLI", "Consumer Disc.":"XLY",
        "Comm. Services":"XLC", "Real Estate":   "XLRE","Utilities":     "XLU",
    }
    sec_data = yf.download(list(sector_tickers.values()), period="2d", progress=False, auto_adjust=True)
    sec_cls  = sec_data["Close"]
    sectors  = []
    for name, ticker in sector_tickers.items():
        if ticker not in sec_cls.columns:
            continue
        col = sec_cls[ticker].dropna()
        if len(col) < 2:
            continue
        pct = ((col.iloc[-1] - col.iloc[-2]) / col.iloc[-2]) * 100
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
        h = yf.Ticker(ticker).history(period="2d")
        if len(h) >= 2:
            prev, close = h["Close"].iloc[-2], h["Close"].iloc[-1]
        else:
            prev = close = h["Close"].iloc[0]
        commodities.append({"name": name, "val": close, "pct": ((close - prev) / prev) * 100})

    # ── S&P 500 YTD performance ───────────────────────────────────────────────
    ytd = fetch_ytd()

    # ── Baseball ──────────────────────────────────────────────────────────────
    baseball = fetch_baseball()

    return {
        "date_str":    date_str,
        "vol_str":     vol_str,
        "indices":     indices,
        "vix":         vix,
        "sectors":     sectors,
        "commodities": commodities,
        "ytd":         ytd,
        "baseball":    baseball,
    }


def fetch_ytd():
    """Pull S&P 500 YTD performance: return, high, low, monthly breakdown, sparkline points."""
    try:
        today = datetime.now()
        jan1  = datetime(today.year, 1, 1)
        h     = yf.Ticker("^GSPC").history(start=jan1.strftime("%Y-%m-%d"))
        if len(h) < 2:
            return None

        open_price  = h["Close"].iloc[0]   # first trading day close as baseline
        close_price = h["Close"].iloc[-1]
        ytd_pct     = ((close_price - open_price) / open_price) * 100
        ytd_pts     = close_price - open_price
        ytd_high    = h["High"].max()
        ytd_low     = h["Low"].min()

        # 52-week high/low
        h52 = yf.Ticker("^GSPC").history(period="1y")
        wk52_high = h52["High"].max()
        wk52_low  = h52["Low"].min()

        # Sparkline: normalize closes to 0-50 range for SVG
        closes_list = h["Close"].tolist()
        mn, mx = min(closes_list), max(closes_list)
        rng = mx - mn if mx != mn else 1
        total = len(closes_list)
        svg_w = 362
        points = []
        for i, c in enumerate(closes_list):
            x = i / (total - 1) * svg_w
            y = 50 - ((c - mn) / rng) * 44   # y=50 is bottom, y=6 is top
            points.append((x, y))

        return {
            "ytd_pct":    ytd_pct,
            "ytd_pts":    ytd_pts,
            "open_price": open_price,
            "close":      close_price,
            "ytd_high":   ytd_high,
            "ytd_low":    ytd_low,
            "wk52_high":  wk52_high,
            "wk52_low":   wk52_low,
            "sparkline":  points,
        }
    except Exception as e:
        print(f"YTD fetch failed: {e}")
        return None


def fetch_baseball():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={yesterday}&hydrate=team"
    games_out = []
    try:
        data  = requests.get(url, timeout=10).json()
        dates = data.get("dates", [])
        if not dates:
            return games_out
        for game in dates[0].get("games", []):
            teams     = game.get("teams", {})
            away_abbr = teams.get("away", {}).get("team", {}).get("abbreviation", "")
            home_abbr = teams.get("home", {}).get("team", {}).get("abbreviation", "")
            if not any(t in BASEBALL_TEAMS for t in [away_abbr, home_abbr]):
                continue
            away_name  = teams.get("away", {}).get("team", {}).get("teamName", away_abbr)
            home_name  = teams.get("home", {}).get("team", {}).get("teamName", home_abbr)
            away_score = teams.get("away", {}).get("score", "-")
            home_score = teams.get("home", {}).get("score", "-")
            games_out.append({
                "away": away_abbr, "away_name": away_name,
                "home": home_abbr, "home_name": home_name,
                "away_score": away_score, "home_score": home_score,
            })
    except Exception as e:
        print(f"Baseball fetch failed: {e}")
    return games_out


# ── Formatting helpers ────────────────────────────────────────────────────────

def arrow(n):    return "▲" if n >= 0 else "▼"
def sign(n):     return "+" if n >= 0 else ""
def cc(n):       return "up" if n >= 0 else "dn"
def fmt(n, d=2): return f"{n:,.{d}f}"


# ── Section HTML builders ─────────────────────────────────────────────────────

def sector_bars_html(sectors):
    if not sectors:
        return ""
    max_abs = max(abs(s["pct"]) for s in sectors)
    html = ""
    for s in sectors:
        pct  = s["pct"]
        w    = abs(pct) / max_abs * 44
        fill = (
            f'<div style="height:100%;background:#111;width:{w}%;margin-left:50%;"></div>'
            if pct >= 0 else
            f'<div style="height:100%;background:#999;width:{w}%;position:absolute;right:50%;"></div>'
        )
        html += f"""
        <div class="br">
          <span class="bl">{s['name']}</span>
          <div class="bt"><div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#ccc;"></div>{fill}</div>
          <span class="bv {cc(pct)}">{sign(pct)}{fmt(pct)}%</span>
        </div>"""
    return html


def mover_rows(stocks):
    rows = ""
    for s in stocks:
        pos = min(max(round(s["wk52_pos"]), 2), 96)  # clamp so dot stays visible
        rows += f"""
        <tr>
          <td><strong>{s['ticker']}</strong><br><span class="wk">{s['ticker']}</span></td>
          <td class="ra">{fmt(s['price'])}</td>
          <td class="ra {cc(s['pct'])}">{sign(s['pct'])}{fmt(s['pct'])}%</td>
          <td class="ra">
            <span class="wk">{fmt(s['wk52_low'], 0)}–{fmt(s['wk52_high'], 0)}</span><br>
            <span class="wkbar"><span class="wkdot" style="left:{pos}%;"></span></span>
          </td>
        </tr>"""
    return rows


def baseball_html(games, date_label):
    if not games:
        return '<div style="padding:12px 16px;font-size:12px;color:#888;">No games found for tracked teams yesterday.</div>'
    rows = ""
    for g in games:
        try:
            a_win = int(g["away_score"]) > int(g["home_score"])
        except:
            a_win = False
        rows += f"""
        <div class="bb-game">
          <div class="bb-team">
            <div class="bb-abbr">{g['away']}</div>
          </div>
          <div class="bb-mid">
            <div class="bb-final">Final</div>
            <div class="bb-scores">
              <span class="bb-score {'bb-win' if a_win else 'bb-loss'}">{g['away_score']}</span>
              <span class="bb-vs">—</span>
              <span class="bb-score {'bb-loss' if a_win else 'bb-win'}">{g['home_score']}</span>
            </div>
          </div>
          <div class="bb-team">
            <div class="bb-abbr">{g['home']}</div>
          </div>
        </div>"""
    return rows


def ytd_html(ytd):
    if not ytd:
        return '<div style="padding:12px 16px;font-size:12px;color:#888;">YTD data unavailable.</div>'

    pct_str = f"{'+' if ytd['ytd_pct'] >= 0 else ''}{ytd['ytd_pct']:.2f}%"
    pts_str = f"{'+' if ytd['ytd_pts'] >= 0 else ''}{ytd['ytd_pts']:,.0f} pts since Jan 1"
    clr     = "#111" if ytd['ytd_pct'] >= 0 else "#888"

    # Sparkline from real price points
    pts = ytd["sparkline"]
    if len(pts) >= 2:
        path_d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
        for x, y in pts[1:]:
            path_d += f" L{x:.1f},{y:.1f}"
        last_x, last_y = pts[-1]
        area_d = f"M{pts[0][0]:.1f},50 " + path_d[1:] + f" L{last_x:.1f},50 Z"
    else:
        path_d = "M0,25 L362,25"
        area_d = ""
        last_x, last_y = 362, 25

    return f"""
    <div style="padding:12px 16px;border-bottom:1px solid #ccc;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
        <div>
          <div style="font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:#888;margin-bottom:1px;">YTD Return</div>
          <div style="font-family:'Playfair Display',serif;font-size:28px;font-weight:900;line-height:1;color:{clr};">{pct_str}</div>
          <div style="font-size:10px;color:#777;margin-top:2px;">{pts_str}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;text-align:right;">
          <div style="font-size:10px;color:#666;">YTD High</div><div style="font-size:10px;font-weight:700;">{ytd['ytd_high']:,.0f}</div>
          <div style="font-size:10px;color:#666;">YTD Low</div><div style="font-size:10px;font-weight:700;">{ytd['ytd_low']:,.0f}</div>
          <div style="font-size:10px;color:#666;">52W High</div><div style="font-size:10px;font-weight:700;">{ytd['wk52_high']:,.0f}</div>
          <div style="font-size:10px;color:#666;">52W Low</div><div style="font-size:10px;font-weight:700;">{ytd['wk52_low']:,.0f}</div>
        </div>
      </div>
      <svg viewBox="0 0 362 52" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:52px;display:block;">
        <defs>
          <linearGradient id="spxGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#111" stop-opacity="0.10"/>
            <stop offset="100%" stop-color="#111" stop-opacity="0.01"/>
          </linearGradient>
        </defs>
        <line x1="0" y1="50" x2="362" y2="50" stroke="#eee" stroke-width="1"/>
        <path d="{area_d}" fill="url(#spxGrad)"/>
        <path d="{path_d}" fill="none" stroke="#111" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="#111"/>
      </svg>
      <div style="display:flex;justify-content:space-between;font-size:8px;color:#bbb;margin-top:3px;">
        <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span><span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span>
      </div>
    </div>"""


def build_html(d):
    indices_html = "".join(f"""
        <div class="ic">
          <div class="in">{idx['name']}</div>
          <div class="iv">{fmt(idx['value'])}</div>
          <div class="ic2 {cc(idx['chg'])}">{arrow(idx['chg'])} {sign(idx['chg'])}{fmt(abs(idx['chg']))} ({sign(idx['pct'])}{fmt(idx['pct'])}%)</div>
        </div>""" for idx in d["indices"])

    comm_html = "".join(
        f'<div class="ci"><span class="cl2">{c["name"]}</span>'
        f'<span class="{cc(c["pct"])}">{sign(c["pct"])}{fmt(c["pct"])}%&nbsp;&nbsp;${fmt(c["val"])}</span></div>'
        for c in d["commodities"]
    )

    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%B %-d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The FiDi Market Close — {d['date_str']}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#f4f4f0;padding:16px 8px;}}
.ew{{font-family:'Libre Baskerville',Georgia,serif;background:#fff;color:#111;max-width:600px;margin:0 auto;border:1px solid #bbb;}}
.eh{{border-bottom:4px double #111;padding:10px 14px 8px;text-align:center;}}
.flag{{font-family:'Playfair Display',Georgia,serif;font-size:clamp(22px,5.5vw,32px);font-weight:900;letter-spacing:-1px;line-height:1;}}
.tagline{{font-size:9px;color:#666;margin:3px 0 4px;line-height:1.4;}}
.tagline a{{color:#111;font-weight:700;text-decoration:none;}}
.hm{{display:flex;justify-content:space-between;font-size:8px;border-top:1px solid #111;border-bottom:1px solid #111;padding:3px 0;margin-top:4px;letter-spacing:.04em;text-transform:uppercase;flex-wrap:wrap;gap:1px;}}
.sl{{font-size:9px;letter-spacing:.16em;text-transform:uppercase;font-weight:700;border-bottom:1px solid #aaa;border-top:2px solid #111;padding:5px 16px;background:#fafafa;}}
.ig{{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #ccc;}}
.ic{{padding:12px 8px;border-right:1px solid #ddd;border-bottom:1px solid #ddd;text-align:center;}}
.ic:nth-child(2n){{border-right:none;}}.ic:nth-child(3),.ic:nth-child(4){{border-bottom:none;}}
@media(min-width:480px){{.ig{{grid-template-columns:repeat(4,1fr);}}.ic{{border-bottom:none;}}.ic:nth-child(2n){{border-right:1px solid #ddd;}}.ic:last-child{{border-right:none;}}}}
.in{{font-size:9px;letter-spacing:.07em;text-transform:uppercase;color:#666;margin-bottom:3px;}}
.iv{{font-family:'Playfair Display',serif;font-size:clamp(15px,3.5vw,18px);font-weight:700;line-height:1.1;}}
.ic2{{font-size:clamp(10px,2.5vw,11.5px);margin-top:2px;}}
.up{{color:#111;}}.dn{{color:#888;}}
.brow{{padding:5px 16px;font-size:clamp(10px,2.5vw,10.5px);color:#555;border-bottom:1px solid #ccc;background:#f9f9f9;display:flex;flex-wrap:wrap;gap:4px 16px;}}
.bb-team{{display:flex;flex-direction:column;align-items:center;width:60px;flex-shrink:0;}}
.bb-abbr{{font-family:'Playfair Display',serif;font-size:18px;font-weight:700;letter-spacing:.02em;}}
.tc{{display:grid;grid-template-columns:1fr;border-bottom:1px solid #ccc;}}
@media(min-width:480px){{.tc{{grid-template-columns:1fr 1fr;}}}}
.cl{{padding:12px 16px;border-bottom:1px solid #ccc;}}.cr{{padding:12px 16px;}}
@media(min-width:480px){{.cl{{border-bottom:none;border-right:1px solid #ccc;}}}}
.ch{{font-size:9px;letter-spacing:.15em;text-transform:uppercase;font-weight:700;border-bottom:1px solid #111;padding-bottom:4px;margin-bottom:6px;}}
.st{{width:100%;border-collapse:collapse;font-size:clamp(10px,2.5vw,11.5px);}}
.st th{{font-size:8.5px;letter-spacing:.06em;text-transform:uppercase;border-bottom:1px solid #aaa;padding-bottom:4px;text-align:left;}}
.st td{{padding:4px 0;border-bottom:1px solid #eee;vertical-align:middle;}}.st tr:last-child td{{border-bottom:none;}}
.ra{{text-align:right;}}.wk{{font-size:9.5px;color:#888;}}
.wkbar{{width:48px;height:5px;background:#eee;display:inline-block;vertical-align:middle;position:relative;margin-left:3px;}}
.wkdot{{position:absolute;top:-2px;height:9px;width:2px;background:#111;}}
.sb{{padding:10px 16px;border-bottom:1px solid #ccc;}}
.br{{display:flex;align-items:center;margin-bottom:6px;font-size:clamp(10px,2.5vw,11px);gap:6px;}}
.bl{{width:100px;flex-shrink:0;}}.bt{{flex:1;height:9px;background:#eee;position:relative;}}.bv{{width:48px;text-align:right;flex-shrink:0;}}
.comm{{padding:10px 16px;border-bottom:1px solid #ccc;}}
.ci{{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #f0f0f0;font-size:clamp(11px,2.8vw,12px);}}
.ci:last-child{{border-bottom:none;}}.cl2{{color:#666;}}
.bb-wrap{{padding:12px 16px;border-bottom:1px solid #ccc;}}
.bb-game{{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;gap:8px;}}
.bb-game:last-child{{border-bottom:none;}}
.bb-team{{display:flex;flex-direction:column;align-items:center;width:80px;flex-shrink:0;}}
.bb-abbr{{font-family:'Playfair Display',serif;font-size:15px;font-weight:700;}}
.bb-name{{font-size:9px;color:#888;letter-spacing:.04em;text-transform:uppercase;margin-top:1px;}}
.bb-score{{font-family:'Playfair Display',serif;font-size:26px;font-weight:900;line-height:1;width:36px;text-align:center;}}
.bb-vs{{font-size:9px;color:#aaa;text-transform:uppercase;letter-spacing:.08em;}}
.bb-mid{{display:flex;flex-direction:column;align-items:center;flex:1;}}
.bb-final{{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:#999;margin-bottom:2px;}}
.bb-scores{{display:flex;align-items:center;gap:6px;}}
.bb-win{{font-weight:700;color:#111;}}.bb-loss{{color:#aaa;}}
.ft{{border-top:3px double #111;padding:10px 16px;font-size:clamp(9px,2.2vw,10px);color:#777;text-align:center;line-height:1.7;}}
.ft a{{color:#888;}}
</style>
</head>
<body>
<div class="ew">

  <div class="eh">
    <div class="flag">The FiDi Market Close</div>
    <div class="tagline">Presented by <a href="https://www.learnatfidi.com">Financial District</a> &nbsp;·&nbsp; We teach kids how to invest &nbsp;·&nbsp; <a href="https://www.learnatfidi.com">LearnAtFidi.com</a></div>
    <div class="hm">
      <span>{d['date_str']}</span>
      <span>Markets · Economy · Capital</span>
    </div>
  </div>

  <div class="sl">Market Indices — Closing Prices</div>
  <div class="ig">{indices_html}</div>

  <div class="sl">S&amp;P 500 — Year to Date {datetime.now().year}</div>
  {ytd_html(d['ytd'])}

  <div class="sl">Sector Performance</div>
  <div class="sb">{sector_bars_html(d['sectors'])}</div>

  <div class="sl">Commodities</div>
  <div class="comm">{comm_html}</div>

  <div class="sl">Last Night's Baseball — {yesterday_str}</div>
  <div class="bb-wrap">{baseball_html(d['baseball'], yesterday_str)}</div>

  <div class="ft">
    <strong>The FiDi Market Close</strong> &bull; Presented by <a href="https://www.learnatfidi.com"><strong>Financial District</strong></a> &bull; <a href="https://www.learnatfidi.com">LearnAtFidi.com</a><br>
    Published Monday–Friday after 4:00 p.m. ET &bull; Not investment advice.<br>
    &copy; 2026 Financial District &bull; <a href="#">Unsubscribe</a> &bull; <a href="#">View in browser</a>
  </div>

</div>
</body>
</html>"""


def main():
    print("Fetching market data...")
    data = fetch()
    print(f"Date: {data['date_str']}")
    print(f"YTD: {data['ytd']['ytd_pct']:.2f}%" if data['ytd'] else "YTD: unavailable")
    print(f"Baseball games: {len(data['baseball'])}")

    html = build_html(data)

    print(f"Sending to {TO_EMAIL}...")
    response = resend.Emails.send({
        "from":    f"The FiDi Market Close <{FROM_EMAIL}>",
        "to":      [TO_EMAIL],
        "subject": f"The FiDi Market Close — {data['date_str']}",
        "html":    html,
    })
    print(f"Sent. ID: {response['id']}")


if __name__ == "__main__":
    main()
