import os
import time
from datetime import datetime, timedelta
import requests
import resend
from google import genai
from google.genai import types

# ==================== CONFIGURATION ====================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "YOUR_NEWSAPI_ORG_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "your_account@gmail.com")

resend.api_key = os.environ.get("RESEND_API_KEY", "YOUR_RESEND_API_KEY")

# Taiwan stock watchlist (market: 'tse' for TWSE, 'otc' for TPEx)
TW_WATCHLIST = {
    "t00": {"name": "加權指數", "market": "tse"},
    "2330": {"name": "台積電", "market": "tse"},
    "0050": {"name": "台灣50", "market": "tse"},
    "00675L": {"name": "富邦正2", "market": "tse"},
    "00631L": {"name": "元大正2", "market": "tse"},
    "00662": {"name": "富邦QQQ", "market": "tse"},
    "1215": {"name": "卜蜂", "market": "tse"},
    "2912": {"name": "統一超", "market": "tse"},
    "1232": {"name": "大統益", "market": "tse"},
    "4772": {"name": "台特化", "market": "otc"},
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
    date_yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
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
    """Generates a list of recent date strings (YYYYMMDD and YYYY/MM/DD) to query backwards."""
    # Convert UTC to Taiwan Time (UTC+8)
    tw_now = datetime.utcnow() + timedelta(hours=8)
    dates = []
    for i in range(lookback_days):
        dt = tw_now - timedelta(days=i)
        dates.append({
            "twse": dt.strftime('%Y%m%d'),          # TWSE format: 20260818
            "tpex": f"{dt.year - 1911}/{dt.strftime('%m/%d')}"  # TPEx ROC format: 115/08/18
        })
    return dates

def fetch_taiwan_stock_summary(watchlist):
    """Fetches real quotes and automatically falls back to latest settled institutional trading."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Fetch Real-time / Daily Quotes from MIS API
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
                close_val = prev_close if (close_raw == "-" or not close_raw) else float(close_raw) if close_raw.replace('.', '', 1).isdigit() else None

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
        print(f"⚠️ Error fetching MIS quotes: {e}")

    # 2. Fetch TAIEX Total Daily Turnover in NTD
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
        print(f"⚠️ Error fetching TAIEX NTD turnover: {e}")

    # 3. Fetch Institutional Trading with Multi-Day Fallback
    institutional_data = {}
    query_dates = get_latest_settled_dates()

    # 3A. TWSE Listed (上市)
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
                            net_shares = int(row[18].replace(',', ''))
                            institutional_data[code] = f"{net_shares // 1000:+,} 張"
                    break  # Successfully found latest published data
        except Exception:
            continue

    # 3B. TPEx OTC (上櫃 - e.g., 4772 台特化)
    for d in query_dates:
        try:
            tpex_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trading/3itrade_hedge_result.php?l=zh-tw&t=D&d={d['tpex']}"
            tpex_resp = requests.get(tpex_url, headers=headers, timeout=10)
            if tpex_resp.status_code == 200:
                json_data = tpex_resp.json()
                if "aaData" in json_data and len(json_data["aaData"]) > 0:
                    for row in json_data["aaData"]:
                        code = row[0].strip()
                        if code in watchlist:
                            net_shares = int(row[14].replace(',', ''))
                            institutional_data[code] = f"{net_shares // 1000:+,} 張"
                    break  # Successfully found latest published data
        except Exception:
            continue

    # 4. Construct HTML Component
    table_rows = ""
    for code, meta in watchlist.items():
        name = meta["name"]
        q = quotes.get(code, {"close": "-", "diff_val": 0, "change": "-", "volume_lots": "-"})
        
        if code == "t00":
            volume_display = taiex_ntd_volume if taiex_ntd_volume else f"{q['volume_lots']} 張"
            total_inst = "市場指數無個股法人"
            inst_color = "#64748b"
        else:
            volume_display = f"{q['volume_lots']} 張"
            total_inst = institutional_data.get(code, "無交易數據")
            inst_color = "#dc2626" if "+" in total_inst else "#16a34a" if "-" in total_inst else "#475569"

        diff_val = q.get("diff_val", 0)
        change_color = "#dc2626" if diff_val > 0 else "#16a34a" if diff_val < 0 else "#475569"

        table_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9; text-align: center; font-size: 13px;">
            <td style="padding: 10px 6px; text-align: left; font-weight: 600;">{name} ({code})</td>
            <td style="padding: 10px 6px; font-weight: bold; color: #0f172a;">{q['close']}</td>
            <td style="padding: 10px 6px; color: {change_color}; font-weight: 600;">{q['change']}</td>
            <td style="padding: 10px 6px; color: #334155;">{volume_display}</td>
            <td style="padding: 10px 6px; color: {inst_color}; font-weight: 600;">{total_inst}</td>
        </tr>
        """

    return f"""
    <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
        <div style="display:inline-block; background-color:#fef3c7; color:#92400e; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:12px; text-transform:uppercase;">📊 Key Taiwan Equities Tracking (台股行情與三大法人)</div>
        <table style="width:100%; border-collapse: collapse; margin-top:8px;">
            <thead>
                <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; font-size: 12px; color: #64748b;">
                    <th style="padding: 8px 6px; text-align: left;">標的名稱</th>
                    <th style="padding: 8px 6px;">收盤價</th>
                    <th style="padding: 8px 6px;">漲跌幅</th>
                    <th style="padding: 8px 6px;">成交金額 / 成交量</th>
                    <th style="padding: 8px 6px;">三大法人買賣超</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p style="font-size: 11px; color: #94a3b8; margin: 8px 0 0 0; text-align: right;">* 買賣超單位：張 (+買超 / -賣超)。若盤中查詢將自動顯示前一已結算交易日之法人籌碼。數據來源：TWSE / TPEx</p>
    </div>
    """

def generate_expanded_matrix_html(raw_news_payload):
    """Uses Gemini to generate the curated news matrix, preserving the stock placeholder."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are an elite corporate intelligence compiler. Analyze the raw recent data feed provided below. Your primary task is to critically evaluate these fresh entries and CHOOSE ONLY the absolute top 3 most important, breaking, high-impact news stories of the last 24 hours for each subject matrix.

    Follow this HTML layout structure precisely, using modern inline CSS:

    <div style="background-color:#f8fafc; padding:30px 15px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#1e293b; max-width:650px; margin:0 auto; border-radius:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
        
        <div style="border-bottom:2px solid #e2e8f0; padding-bottom:15px; margin-bottom:25px;">
            <h1 style="margin:0; font-size:24px; color:#0f172a; font-weight:800; letter-spacing:-0.025em;">🌟 Daily Executive Intelligence Briefing</h1>
            <p style="margin:5px 0 0 0; font-size:14px; color:#64748b;">Curated top strategic events and developments from the last 24 hours.</p>
        </div>

        <div style="background-color:#eff6ff; border-left:4px solid #3b82f6; padding:15px; border-radius:0 8px 8px 0; margin-bottom:30px;">
            <h3 style="margin:0 0 8px 0; font-size:14px; text-transform:uppercase; letter-spacing:0.05em; color:#1d4ed8; font-weight:700;">Executive Summary</h3>
            <p style="margin:0; font-size:14px; line-height:1.6; color:#1e3a8a;">[INSERT 2-3 SENTENCE GLOBAL IMPACT SUMMARY OF THE BREAKING MOVES HERE IN ENGLISH]</p>
        </div>

        <!-- STOCK_SECTION_PLACEHOLDER -->

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
            <div style="display:inline-block; background-color:#f0fdf4; color:#166534; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">📈 Stock Markets & Finance</div>
            <img src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="Finance" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Market (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES FROM PAST 24H IN TRADITIONAL CHINESE]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Market (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES FROM PAST 24H IN ENGLISH]
            </ul>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
            <div style="display:inline-block; background-color:#fef2f2; color:#991b1b; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">🧠 Artificial Intelligence & Tech</div>
            <img src="https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="AI Tech" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Tech Ecosystem (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES FROM PAST 24H IN TRADITIONAL CHINESE]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Innovation (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN ENGLISH BULLETS]
            </ul>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:15px;">
            <div style="display:inline-block; background-color:#eff6ff; color:#1e40af; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">📡 Wireless Communications (5G/6G)</div>
            <img src="https://images.unsplash.com/photo-1562408590-e32931084e23?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="Wireless Infrastructure" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Telco Networks (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TRADITIONAL CHINESE BULLETS]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Infrastructure (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN ENGLISH BULLETS]
            </ul>
        </div>

    </div>

    CRITICAL INSTRUCTIONS:
    - Retain the exact comment line <!-- STOCK_SECTION_PLACEHOLDER --> without removing or replacing it.
    - Substitute placeholders with actual curated news facts from the source feed.
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
            "subject": "🌟 24-Hour Executive Strategic Curation Digest & Market Tracker",
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

    print("📈 Fetching Taiwan stock price, changes, NTD volume, and institutional data...")
    stock_section_html = fetch_taiwan_stock_summary(TW_WATCHLIST)

    print("🛰️ Harvesting targeted news category arrays from past 24 hours...")
    master_feed = ""
    for category_name, query_string in CATEGORIES.items():
        master_feed += f"\n=== BATCH: {category_name.upper()} ===\n"
        master_feed += fetch_category_news(query_string) + "\n"
        
    print("🧠 Chief Editor Model: Extracting top stories and formatting matrix...")
    report_html = generate_expanded_matrix_html(master_feed)
    
    # Directly inject the exact python-generated stock table into the template
    if "<!-- STOCK_SECTION_PLACEHOLDER -->" in report_html:
        final_email_html = report_html.replace("<!-- STOCK_SECTION_PLACEHOLDER -->", stock_section_html)
    else:
        # Fallback in case LLM removed comment
        final_email_html = report_html + stock_section_html

    send_resend_email(final_email_html)

if __name__ == "__main__":
    main()
