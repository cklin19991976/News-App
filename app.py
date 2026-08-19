import os
import time
from datetime import datetime, timedelta, timezone
import requests
import resend
from google import genai
from google.genai import types

# ==================== CONFIGURATION ====================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "YOUR_NEWSAPI_ORG_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "your_account@gmail.com")

resend.api_key = os.environ.get("RESEND_API_KEY", "YOUR_RESEND_API_KEY")

# Target assets for Week & Month KD analysis
KD_WATCHLIST = {
    "SPY": {"name": "S&P500 SPY", "ticker": "SPY"},
    "QQQ": {"name": "Nasdaq100 QQQ", "ticker": "QQQ"},
    "SOX": {"name": "費城半導體 SOX", "ticker": "^SOX"},
    "t00": {"name": "台灣加權指數", "ticker": "^TWII"},
    "0050": {"name": "元大台灣50", "ticker": "0050.TW"},
    "2330": {"name": "台積電", "ticker": "2330.TW"},
    "1215": {"name": "卜蜂", "ticker": "1215.TW"},
    "4772": {"name": "台特化", "ticker": "4772.TWO"},
    "1232": {"name": "大統益", "ticker": "1232.TW"},
}

# Taiwan stock watchlist for Quotes, Flow & MAs
TW_WATCHLIST = {
    "t00": {"name": "台灣加權指數", "market": "tse", "yf_ticker": "^TWII"},
    "2330": {"name": "台積電", "market": "tse", "yf_ticker": "2330.TW"},
    "0050": {"name": "元大0050", "market": "tse", "yf_ticker": "0050.TW"},
    "00675L": {"name": "富邦正2", "market": "tse", "yf_ticker": "00675L.TW"},
    "00631L": {"name": "元大正2", "market": "tse", "yf_ticker": "00631L.TW"},
    "00662": {"name": "富邦QQQ", "market": "tse", "yf_ticker": "00662.TW"},
    "1215": {"name": "卜蜂", "market": "tse", "yf_ticker": "1215.TW"},
    "2912": {"name": "統一超", "market": "tse", "yf_ticker": "2912.TW"},
    "1232": {"name": "大統益", "market": "tse", "yf_ticker": "1232.TW"},
    "4772": {"name": "台特化", "market": "otc", "yf_ticker": "4772.TWO"},
}

CATEGORIES = {
    "Taiwan_Finance": "taiwan AND (market OR finance OR stock)",
    "Taiwan_Tech": "taiwan AND (AI OR semiconductor OR tech)",
    "US_Finance": "us AND (fed OR bonds OR dow OR nasdaq)",
    "US_Tech": "us AND (nvidia OR tech OR \"artificial intelligence\")",
    "Wireless": "(5G OR 6G OR telecom OR wireless)"
}
# =======================================================

def fetch_category_news(query_string):
    """Fetches real articles using clean YYYY-MM-DD parameters for free tier stability."""
    url = "https://newsapi.org/v2/everything"
    date_yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    params = {
        "q": query_string,
        "sortBy": "relevancy",  
        "from": date_yesterday,
        "language": "en",
        "pageSize": 20,         
        "apiKey": NEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        formatted_news = []
        
        for art in articles:
            title = art.get("title", "")
            source = art.get("source", {}).get("name", "Unknown")
            description = art.get("description", "")
            article_url = art.get("url", "#")
            
            if title and title != "[Removed]" and "No Title" not in title:
                formatted_news.append(f"[{source}] {title}\nSummary: {description}\nLink: {article_url}")
                
        return "\n\n".join(formatted_news) if formatted_news else "No specific articles found for this category loop."
    except Exception as e:
        return f"Error gathering data: {e}"

def get_latest_settled_dates(lookback_days=5):
    """Generates a list of recent date strings without using deprecated utcnow."""
    tw_now = datetime.now(timezone.utc) + timedelta(hours=8)
    dates = []
    for i in range(lookback_days):
        dt = tw_now - timedelta(days=i)
        dates.append({
            "twse": dt.strftime('%Y%m%d'),
            "tpex": f"{dt.year - 1911}/{dt.strftime('%m/%d')}"
        })
    return dates

def calculate_kd_series(highs, lows, closes, period=9):
    """Computes classic KD (9, 3, 3) stochastic indicators and returns (curr_k, curr_d, prev_k, prev_d)."""
    if len(closes) < period + 1:
        return None, None, None, None
    
    k = 50.0
    d = 50.0
    k_history = []
    d_history = []
    
    for i in range(len(closes)):
        if i < period - 1:
            k_history.append(50.0)
            d_history.append(50.0)
            continue
            
        window_highs = highs[i - period + 1 : i + 1]
        window_lows = lows[i - period + 1 : i + 1]
        
        hn = max(window_highs)
        ln = min(window_lows)
        cn = closes[i]
        
        rsv = ((cn - ln) / (hn - ln) * 100.0) if hn != ln else 50.0
        k = (2.0 / 3.0) * k + (1.0 / 3.0) * rsv
        d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
        k_history.append(k)
        d_history.append(d)
        
    return round(k_history[-1], 2), round(d_history[-1], 2), round(k_history[-2], 2), round(d_history[-2], 2)

def fetch_kd_info(ticker, interval, range_str):
    """Fetches high, low, close data and calculates current & previous K, D values."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_str}&interval={interval}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        chart_result = data.get("chart", {}).get("result")
        if not chart_result:
            return None
        
        quotes = chart_result[0].get("indicators", {}).get("quote", [])[0]
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        
        clean_highs, clean_lows, clean_closes = [], [], []
        for h, l, c in zip(highs, lows, closes):
            if h is not None and l is not None and c is not None:
                clean_highs.append(float(h))
                clean_lows.append(float(l))
                clean_closes.append(float(c))
                
        curr_k, curr_d, prev_k, prev_d = calculate_kd_series(clean_highs, clean_lows, clean_closes, period=9)
        if curr_k is None:
            return None
            
        return {
            "k": curr_k,
            "d": curr_d,
            "prev_k": prev_k,
            "prev_d": prev_d,
            "is_bullish": curr_k > curr_d,
            "is_golden_cross": (prev_k <= prev_d and curr_k > curr_d),
            "is_death_cross": (prev_k >= prev_d and curr_k < curr_d),
            "is_reversing_up": (curr_k > prev_k and curr_k < 40)
        }
    except Exception as e:
        print(f"⚠️ Warning: KD calculation error for {ticker} ({interval}): {e}")
        return None

def analyze_multi_kd_strategy(day_kd, week_kd, month_kd):
    """
    Evaluates '長看趨勢、短找買點' (Long trend, short trigger) Multi-Timeframe KD Strategy:
    1. 最佳買點（長多短回）：月 KD 維持向上 + 周 KD 低檔金叉 + 日 KD 由低點反轉。
    2. 避免陷阱（逆勢摸底）：月 KD、周 KD 持續向下/死叉，日 KD 低檔金叉/超賣 (反彈容易破底)。
    """
    if not month_kd or not week_kd or not day_kd:
        return "<span style='color:#64748b;'>資料不足</span>"

    month_bullish = month_kd["is_bullish"] or (month_kd["k"] > month_kd["prev_k"])
    week_low_golden = (week_kd["is_golden_cross"] and week_kd["k"] <= 55) or (week_kd["is_bullish"] and week_kd["k"] < 50)
    day_rebound = day_kd["is_reversing_up"] or day_kd["is_golden_cross"] or (day_kd["k"] > day_kd["prev_k"] and day_kd["k"] <= 40)

    # 1. 最佳買點 (長多短回)
    if month_bullish and week_low_golden and day_rebound:
        return """<span style="background-color:#fee2e2; color:#b91c1c; padding:3px 6px; border-radius:4px; font-weight:800; border:1px solid #f87171;">🎯 最佳買點 (長多短回)</span>"""

    # 2. 避免陷阱 (逆勢摸底)
    month_bearish = not month_kd["is_bullish"]
    week_bearish = not week_kd["is_bullish"] or week_kd["is_death_cross"]
    day_oversold_bounce = day_kd["k"] <= 30 or day_kd["is_golden_cross"]

    if month_bearish and week_bearish and day_oversold_bounce:
        return """<span style="background-color:#fef2f2; color:#991b1b; padding:3px 6px; border-radius:4px; font-weight:800; border:1px solid #fca5a5;">⚠️ 避免陷阱 (逆勢摸底)</span>"""

    # Other lifecycle stages
    if month_bullish and week_kd["is_bullish"] and week_kd["k"] >= 80:
        return """<span style="background-color:#ffedd5; color:#c2410c; padding:3px 6px; border-radius:4px; font-weight:700;">🚀 強勢主升 (高檔鈍化)</span>"""
    elif month_bullish and week_kd["is_bullish"]:
        return """<span style="background-color:#eff6ff; color:#1d4ed8; padding:3px 6px; border-radius:4px; font-weight:700;">📈 多方波段延續</span>"""
    elif month_bearish and week_bearish:
        return """<span style="background-color:#f1f5f9; color:#475569; padding:3px 6px; border-radius:4px; font-weight:600;">📉 空方整理結構</span>"""
    
    return """<span style="color:#64748b; font-weight:500;">⚖️ 區間震盪觀望</span>"""

def fetch_kd_section_html(watchlist):
    """Generates the Day/Week/Month KD table with Strategy Signals & Overbought/Oversold Badges."""
    rows = ""
    for code, meta in watchlist.items():
        name = meta["name"]
        ticker = meta["ticker"]
        
        d_info = fetch_kd_info(ticker, "1d", "6mo")
        w_info = fetch_kd_info(ticker, "1wk", "2y")
        m_info = fetch_kd_info(ticker, "1mo", "5y")
        
        strategy_badge = analyze_multi_kd_strategy(d_info, w_info, m_info)
        
        def render_kd_badge(kd_dict):
            if not kd_dict:
                return "<span style='color:#94a3b8;'>-</span>"
            
            k_val = kd_dict["k"]
            d_val = kd_dict["d"]
            kd_str = f"K:{k_val:.1f} D:{d_val:.1f}"
            
            cross_tag = " ↑金叉" if kd_dict["is_golden_cross"] else " ↓死叉" if kd_dict["is_death_cross"] else ""
            
            # Overbought (> 80)
            if k_val >= 80 or d_val >= 80:
                return f"""<span style="background-color:#fee2e2; color:#991b1b; padding:3px 5px; border-radius:4px; font-weight:700;">{kd_str}{cross_tag} (超買)</span>"""
            # Oversold (< 20)
            elif k_val <= 20 or d_val <= 20:
                return f"""<span style="background-color:#dcfce7; color:#166534; padding:3px 5px; border-radius:4px; font-weight:700;">{kd_str}{cross_tag} (超賣)</span>"""
            return f"""<span style="color:#334155; font-weight:500;">{kd_str}{cross_tag}</span>"""

        rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9; text-align: center; font-size: 12px;">
            <td style="padding: 10px 6px; text-align: left; font-weight: 600;">{name}</td>
            <td style="padding: 10px 6px;">{render_kd_badge(d_info)}</td>
            <td style="padding: 10px 6px;">{render_kd_badge(w_info)}</td>
            <td style="padding: 10px 6px;">{render_kd_badge(m_info)}</td>
            <td style="padding: 10px 6px;">{strategy_badge}</td>
        </tr>
        """

    return f"""
    <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:20px;">
        <div style="display:inline-block; background-color:#fae8ff; color:#86198f; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:12px; text-transform:uppercase;">⚡ Multi-Timeframe KD Strategy (長看趨勢、短找買點策略矩陣)</div>
        <table style="width:100%; border-collapse: collapse; margin-top:6px;">
            <thead>
                <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; font-size: 11px; color: #64748b;">
                    <th style="padding: 8px 6px; text-align: left;">追蹤標的</th>
                    <th style="padding: 8px 6px;">日 KD (短線反轉)</th>
                    <th style="padding: 8px 6px;">周 KD (波段買點)</th>
                    <th style="padding: 8px 6px;">月 KD (長線大趨勢)</th>
                    <th style="padding: 8px 6px;">多週期策略訊號</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <div style="margin-top: 10px; padding: 10px; background-color: #f8fafc; border-radius: 6px; font-size: 11px; color: #475569; line-height: 1.5;">
            💡 <strong>策略邏輯指引：</strong><br/>
            • <span style="color:#b91c1c; font-weight:bold;">🎯 最佳買點（長多短回）</span>：月 KD 維持多頭 + 周 KD 低檔金叉起漲 + 日 KD 由低點反轉向上。<br/>
            • <span style="color:#991b1b; font-weight:bold;">⚠️ 避免陷阱（逆勢摸底）</span>：月 KD & 周 KD 同步空頭死叉向下時，即使「日 KD」超賣低檔金叉，僅為短線弱勢反彈，破底風險極高。
        </div>
    </div>
    """

def fetch_stock_moving_averages(ticker):
    """Defensively fetches historical closing data and computes moving averages."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
    
    ma_windows = [5, 10, 20, 60, 120, 240]
    result = {f"MA{w}": {"val": "-", "cross": None} for w in ma_windows}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return result
        
        data = resp.json()
        chart_result = data.get("chart", {}).get("result")
        if not chart_result or len(chart_result) == 0:
            return result
        
        indicators = chart_result[0].get("indicators", {}).get("quote", [])
        if not indicators or "close" not in indicators[0]:
            return result

        closes = indicators[0].get("close", [])
        clean_closes = [float(c) for c in closes if c is not None]
        
        if len(clean_closes) < 2:
            return result
            
        curr_price = clean_closes[-1]
        prev_price = clean_closes[-2]
        
        for w in ma_windows:
            if len(clean_closes) >= w:
                curr_ma = sum(clean_closes[-w:]) / w
                prev_ma = sum(clean_closes[-(w + 1):-1]) / w
                
                cross = None
                if prev_price <= prev_ma and curr_price > curr_ma:
                    cross = "UP"
                elif prev_price >= prev_ma and curr_price < curr_ma:
                    cross = "DOWN"
                    
                result[f"MA{w}"] = {
                    "val": f"{curr_ma:,.2f}",
                    "cross": cross
                }
    except Exception as e:
        print(f"⚠️ Warning: MA calculation skipped for {ticker} ({e})")
        
    return result

def fetch_taiwan_stock_summary(watchlist):
    """Fetches real quotes, institutional flows, and moving average matrix safely."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Fetch Real-time Quotes
    symbols_query = "|".join([f"{meta['market']}_{code}.tw" for code, meta in watchlist.items()])
    quote_url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={symbols_query}&json=1&delay=0"
    
    quotes = {}
    try:
        q_resp = requests.get(quote_url, headers=headers, timeout=10)
        if q_resp.status_code == 200:
            q_data = q_resp.json().get("msgArray", [])
            for item in q_data:
                code = item.get("c")
                prev_close = float(item.get("y", 0)) if item.get("y") and item.get("y") != "-" else None
                close_raw = item.get("z", "-")
                close_val = prev_close if (close_raw == "-" or not close_raw) else float(close_raw) if str(close_raw).replace('.', '', 1).isdigit() else None

                change_str = "-"
                change_pct_str = ""
                diff_val = 0
                if close_val is not None and prev_close is not None and prev_close > 0:
                    diff_val = close_val - prev_close
                    pct_val = (diff_val / prev_close) * 100
                    change_str = f"{diff_val:+.2f}"
                    change_pct_str = f"({pct_val:+.2f}%)"

                quotes[code] = {
                    "close": f"{close_val:,.2f}" if close_val is not None else "-",
                    "diff_val": diff_val,
                    "change": f"{change_str} {change_pct_str}".strip(),
                    "volume_lots": f"{int(item.get('v', 0)):,}" if str(item.get('v', '')).isdigit() else "-"
                }
    except Exception as e:
        print(f"⚠️ Warning: Error fetching MIS quotes: {e}")

    # 2. Fetch TAIEX Turnover in NTD
    taiex_ntd_volume = None
    try:
        fmtqik_url = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?response=json"
        fmt_resp = requests.get(fmtqik_url, headers=headers, timeout=10)
        if fmt_resp.status_code == 200:
            fmt_data = fmt_resp.json().get("data", [])
            if fmt_data:
                turnover_ntd = int(fmt_data[-1][2].replace(',', ''))
                taiex_ntd_volume = f"NT$ {turnover_ntd / 1e8:,.2f} 億"
    except Exception as e:
        print(f"⚠️ Warning: Error fetching TAIEX NTD turnover: {e}")

    # 3. Fetch Institutional Data
    institutional_data = {}
    query_dates = get_latest_settled_dates()

    # 3A. TWSE Listed
    for d in query_dates:
        try:
            twse_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d['twse']}&selectType=ALL&response=json"
            twse_resp = requests.get(twse_url, headers=headers, timeout=10)
            if twse_resp.status_code == 200:
                json_data = twse_resp.json()
                if json_data.get("stat") == "OK" and "data" in json_data:
                    for row in json_data["data"]:
                        code = row[0].strip()
                        if code in watchlist:
                            foreign_shares = int(row[4].replace(',', ''))
                            total_shares = int(row[18].replace(',', ''))
                            institutional_data[code] = {
                                "foreign": f"{foreign_shares // 1000:+,} 張",
                                "total": f"{total_shares // 1000:+,} 張"
                            }
                    break
        except Exception:
            continue

    # 3B. TPEx OTC (e.g. 4772)
    for d in query_dates:
        try:
            tpex_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=EW&t=D&d={d['tpex']}"
            tpex_resp = requests.get(tpex_url, headers=headers, timeout=10)
            if tpex_resp.status_code == 200:
                json_data = tpex_resp.json()
                rows = json_data.get("aaData", [])
                if rows:
                    for row in rows:
                        code = str(row[0]).strip()
                        if code in watchlist:
                            foreign_shares = int(str(row[7]).replace(',', '').strip())
                            total_shares = int(str(row[-1]).replace(',', '').strip())
                            institutional_data[code] = {
                                "foreign": f"{foreign_shares // 1000:+,} 張",
                                "total": f"{total_shares // 1000:+,} 張"
                            }
                    break
        except Exception:
            continue

    # 4. Fetch Moving Averages
    ma_results = {}
    for code, meta in watchlist.items():
        ma_results[code] = fetch_stock_moving_averages(meta["yf_ticker"])

    # 5. Build HTML Table 1: Equities & Institutional Flows
    table_rows = ""
    for code, meta in watchlist.items():
        name = meta["name"]
        q = quotes.get(code, {"close": "-", "diff_val": 0, "change": "-", "volume_lots": "-"})
        inst_entry = institutional_data.get(code, {"foreign": "-", "total": "-"})

        if code == "t00":
            volume_display = taiex_ntd_volume if taiex_ntd_volume else f"{q['volume_lots']} 張"
            foreign_inst = "-"
            total_inst = "-"
            foreign_color = "#64748b"
            inst_color = "#64748b"
        else:
            volume_display = f"{q['volume_lots']} 張"
            foreign_inst = inst_entry.get("foreign", "無數據")
            total_inst = inst_entry.get("total", "無數據")
            foreign_color = "#dc2626" if "+" in foreign_inst else "#16a34a" if "-" in foreign_inst else "#475569"
            inst_color = "#dc2626" if "+" in total_inst else "#16a34a" if "-" in total_inst else "#475569"

        diff_val = q.get("diff_val", 0)
        change_color = "#dc2626" if diff_val > 0 else "#16a34a" if diff_val < 0 else "#475569"

        table_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9; text-align: center; font-size: 13px;">
            <td style="padding: 10px 6px; text-align: left; font-weight: 600;">{name} ({code})</td>
            <td style="padding: 10px 6px; font-weight: bold; color: #0f172a;">{q['close']}</td>
            <td style="padding: 10px 6px; color: {change_color}; font-weight: 600;">{q['change']}</td>
            <td style="padding: 10px 6px; color: #334155;">{volume_display}</td>
            <td style="padding: 10px 6px; color: {foreign_color}; font-weight: 600;">{foreign_inst}</td>
            <td style="padding: 10px 6px; color: {inst_color}; font-weight: 600;">{total_inst}</td>
        </tr>
        """

    # 6. Build HTML Table 2: MA Matrix & Alerts
    ma_table_rows = ""
    for code, meta in watchlist.items():
        name = meta["name"]
        ma = ma_results.get(code, {})
        
        def format_ma_cell(ma_dict):
            val = ma_dict.get("val", "-")
            cross = ma_dict.get("cross")
            if cross == "UP":
                return f"""<span style="background-color:#fee2e2; color:#b91c1c; padding:2px 4px; border-radius:4px; font-weight:700;">{val} ↑突破</span>"""
            elif cross == "DOWN":
                return f"""<span style="background-color:#dcfce7; color:#15803d; padding:2px 4px; border-radius:4px; font-weight:700;">{val} ↓跌破</span>"""
            return f"""<span style="color:#334155;">{val}</span>"""

        ma_table_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9; text-align: center; font-size: 12px;">
            <td style="padding: 8px 4px; text-align: left; font-weight: 600;">{name}</td>
            <td style="padding: 8px 4px;">{format_ma_cell(ma.get('MA5', {}))}</td>
            <td style="padding: 8px 4px;">{format_ma_cell(ma.get('MA10', {}))}</td>
            <td style="padding: 8px 4px;">{format_ma_cell(ma.get('MA20', {}))}</td>
            <td style="padding: 8px 4px;">{format_ma_cell(ma.get('MA60', {}))}</td>
            <td style="padding: 8px 4px;">{format_ma_cell(ma.get('MA120', {}))}</td>
            <td style="padding: 8px 4px;">{format_ma_cell(ma.get('MA240', {}))}</td>
        </tr>
        """

    return f"""
    <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:20px;">
        <div style="display:inline-block; background-color:#fef3c7; color:#92400e; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:12px; text-transform:uppercase;">📊 Key Taiwan Equities (台股行情與法人動向)</div>
        <table style="width:100%; border-collapse: collapse; margin-top:8px;">
            <thead>
                <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; font-size: 12px; color: #64748b;">
                    <th style="padding: 8px 6px; text-align: left;">標的名稱</th>
                    <th style="padding: 8px 6px;">收盤價</th>
                    <th style="padding: 8px 6px;">漲跌幅</th>
                    <th style="padding: 8px 6px;">成交金額 / 量</th>
                    <th style="padding: 8px 6px;">外資買賣超</th>
                    <th style="padding: 8px 6px;">三大法人買賣超</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p style="font-size: 11px; color: #94a3b8; margin: 8px 0 0 0; text-align: right;">* 買賣超單位：張 (+買超 / -賣超)。大盤成交量為總成交金額。</p>
    </div>

    <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
        <div style="display:inline-block; background-color:#e0e7ff; color:#3730a3; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:12px; text-transform:uppercase;">📈 Technical Moving Averages & Cross Alerts (均線穿越指標)</div>
        <table style="width:100%; border-collapse: collapse; margin-top:8px;">
            <thead>
                <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; font-size: 11px; color: #64748b;">
                    <th style="padding: 6px 4px; text-align: left;">標的</th>
                    <th style="padding: 6px 4px;">5MA (週)</th>
                    <th style="padding: 6px 4px;">10MA (雙週)</th>
                    <th style="padding: 6px 4px;">20MA (月)</th>
                    <th style="padding: 6px 4px;">60MA (季)</th>
                    <th style="padding: 6px 4px;">120MA (半年)</th>
                    <th style="padding: 6px 4px;">240MA (年)</th>
                </tr>
            </thead>
            <tbody>
                {ma_table_rows}
            </tbody>
        </table>
        <p style="font-size: 11px; color: #94a3b8; margin: 8px 0 0 0; text-align: right;">* 標示說明：<span style="color:#b91c1c; font-weight:bold;">↑突破</span>（收盤價向上突破該均線）；<span style="color:#15803d; font-weight:bold;">↓跌破</span>（收盤價向下跌破該均線）。</p>
    </div>
    """

def generate_expanded_matrix_html(raw_news_payload):
    """Uses Gemini to generate the curated news matrix and Executive Summary."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are an elite corporate intelligence compiler. Analyze the raw recent data feed provided below. Your primary task is to critically evaluate these fresh entries and CHOOSE ONLY the absolute top 3 most important, breaking, high-impact news stories of the last 24 hours for each subject matrix.

    CRITICAL LINKING RULE:
    Every bullet point MUST include an active clickable hyperlink pointing to the article's actual source URL found in the raw data pool (`Link: ...`).
    - Traditional Chinese format: <li style="margin-bottom:8px;"><strong>Headline Title</strong> — Description summary sentence. <a href="ACTUAL_URL" target="_blank" style="color:#2563eb; text-decoration:none; font-size:12px; font-weight:600;">[來源連結]</a></li>
    - English format: <li style="margin-bottom:8px;"><strong>Headline Title</strong> — Description summary sentence. <a href="ACTUAL_URL" target="_blank" style="color:#2563eb; text-decoration:none; font-size:12px; font-weight:600;">[Source Link]</a></li>

    Follow this HTML layout structure precisely, using modern inline CSS:

    <div style="background-color:#f8fafc; padding:30px 15px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#1e293b; max-width:650px; margin:0 auto; border-radius:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
        
        <div style="border-bottom:2px solid #e2e8f0; padding-bottom:15px; margin-bottom:25px;">
            <h1 style="margin:0; font-size:24px; color:#0f172a; font-weight:800; letter-spacing:-0.025em;">🌟 Daily Executive Intelligence Briefing</h1>
            <p style="margin:5px 0 0 0; font-size:14px; color:#64748b;">Curated top strategic events and developments from the last 24 hours.</p>
        </div>

        <!-- TOP_KD_PLACEHOLDER -->
        <!-- STOCK_SECTION_PLACEHOLDER -->

        <!-- EXECUTIVE SUMMARY (POSITIONED AFTER MA SECTION) -->
        <div style="background-color:#eff6ff; border-left:4px solid #3b82f6; padding:15px; border-radius:0 8px 8px 0; margin-bottom:25px;">
            <h3 style="margin:0 0 8px 0; font-size:14px; text-transform:uppercase; letter-spacing:0.05em; color:#1d4ed8; font-weight:700;">Executive Summary</h3>
            <p style="margin:0; font-size:14px; line-height:1.6; color:#1e3a8a;">[INSERT 2-3 SENTENCE GLOBAL IMPACT SUMMARY OF THE BREAKING MOVES HERE IN ENGLISH]</p>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
            <div style="display:inline-block; background-color:#f0fdf4; color:#166534; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">📈 Stock Markets & Finance</div>
            <img src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="Finance" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Market (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES IN TRADITIONAL CHINESE WITH [來源連結]]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Market (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES IN ENGLISH WITH [Source Link]]
            </ul>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
            <div style="display:inline-block; background-color:#fef2f2; color:#991b1b; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">🧠 Artificial Intelligence & Tech</div>
            <img src="https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="AI Tech" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Tech Ecosystem (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES IN TRADITIONAL CHINESE WITH [來源連結]]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Innovation (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES IN ENGLISH WITH [Source Link]]
            </ul>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:15px;">
            <div style="display:inline-block; background-color:#eff6ff; color:#1e40af; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">📡 Wireless Communications (5G/6G)</div>
            <img src="https://images.unsplash.com/photo-1562408590-e32931084e23?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="Wireless Infrastructure" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Telco Networks (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES IN TRADITIONAL CHINESE WITH [來源連結]]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Infrastructure (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES IN ENGLISH WITH [Source Link]]
            </ul>
        </div>

    </div>

    CRITICAL INSTRUCTIONS:
    - Retain the exact comment lines <!-- TOP_KD_PLACEHOLDER --> and <!-- STOCK_SECTION_PLACEHOLDER --> without removing or replacing them.
    - Every selected story item MUST have a valid source link tag matching the URL provided in the raw data pool.
    - Taiwan content sections must be in native Traditional Chinese (繁體中文). USA sections and the Overview must be in English.
    - Apply professional inline email CSS styling. Omit all ```html wrappers. Output only raw inner HTML.

    Raw data pool from last 24 hours:
    {raw_news_payload}
    """
    
    max_retries = 3
    delay = 5  
    api_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=api_config
            )
            return response.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
                print(f"⚠️ Service rate-limited (Attempt {attempt + 1}/{max_retries}). Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  
            else:
                return f"<h2>Error creating intelligence report</h2><p>{e}</p>"
                
    return "<h2>Error: Gemini API remained unavailable after multiple retry attempts.</h2>"

def send_resend_email(html_content):
    """Sends the curated intelligence newsletter using Resend API."""
    try:
        print("🚀 Requesting email delivery via Resend API securely...")
        params = {
            "from": "NewsEngine <onboarding@resend.dev>",
            "to": [RECIPIENT_EMAIL],
            "subject": "🌟 24-Hour Executive Strategic Curation Digest & Technical Market Tracker",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        print("✅ Success! Email brief dispatched successfully.")
    except Exception as e:
        print(f"❌ Resend API System Error: {e}")

def main():
    if "YOUR_" in NEWS_API_KEY or "YOUR_" in GEMINI_API_KEY or "YOUR_" in resend.api_key:
        print("❌ Configuration Missing.")
        return

    print("⚡ Computing Day/Week/Month KD & Multi-Cycle Strategy for SOX, SPY, QQQ, TAIEX, 0050, TSMC...")
    top_kd_html = fetch_kd_section_html(KD_WATCHLIST)

    print("📈 Fetching Taiwan stock quotes, institutional data, and moving average crossovers...")
    stock_section_html = fetch_taiwan_stock_summary(TW_WATCHLIST)

    print("🛰️ Harvesting targeted news category arrays from past 24 hours...")
    master_feed = ""
    for category_name, query_string in CATEGORIES.items():
        master_feed += f"\n=== BATCH: {category_name.upper()} ===\n"
        master_feed += fetch_category_news(query_string) + "\n"
        
    print("🧠 Chief Editor Model: Extracting top stories and formatting matrix...")
    report_html = generate_expanded_matrix_html(master_feed)
    
    # Inject components into their respective positions
    final_email_html = report_html
    if "<!-- TOP_KD_PLACEHOLDER -->" in final_email_html:
        final_email_html = final_email_html.replace("<!-- TOP_KD_PLACEHOLDER -->", top_kd_html)
    else:
        final_email_html = top_kd_html + final_email_html

    if "<!-- STOCK_SECTION_PLACEHOLDER -->" in final_email_html:
        final_email_html = final_email_html.replace("<!-- STOCK_SECTION_PLACEHOLDER -->", stock_section_html)
    else:
        final_email_html += stock_section_html

    send_resend_email(final_email_html)

if __name__ == "__main__":
    main()
