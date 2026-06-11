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

# Robust keyword queries that play nice with NewsAPI free tier matching logic
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
    
    # 🛠️ FIXED: Use simple calendar day syntax instead of complex hourly ISO strings
    date_yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    params = {
        "q": query_string,
        "sortBy": "relevancy",  
        "from": date_yesterday, # Clean date structure accepted by developer keys
        "language": "en",
        "pageSize": 20,         
        "apiKey": NEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        formatted_news = []
        
        for art in articles:
            title = art.get("title", "")
            source = art.get("source", {}).get("name", "Unknown")
            description = art.get("description", "")
            article_url = art.get("url", "#")
            
            # Avoid blank entries or removed articles
            if title and title != "[Removed]" and "No Title" not in title:
                formatted_news.append(f"[{source}] {title}\nSummary: {description}\nLink: {article_url}")
                
        # Fallback tracking if a specific category returns empty
        return "\n\n".join(formatted_news) if formatted_news else "No specific articles found for this category loop."
    except Exception as e:
        return f"Error gathering data: {e}"

def generate_expanded_matrix_html(raw_news_payload):
    """Uses Gemini to filter, force-rank, and construct a high-impact news matrix."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are an elite corporate intelligence compiler. Analyze the raw recent data feed provided below. Your primary task is to critically evaluate these fresh entries and CHOOSE ONLY the absolute top 3 most important, breaking, high-impact news stories of the last 24 hours for each subject matrix. Do not output placeholder filler text. Even if data seems sparse, find the most impactful events inside the text.

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

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
            <div style="display:inline-block; background-color:#f0fdf4; color:#166534; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">📈 Stock Markets & Finance</div>
            <img src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="Finance" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Market (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES FROM PAST 24H IN TRADITIONAL CHINESE. FORMAT EACH AS: <li style="margin-bottom:8px;"><strong>Headline Title</strong> — Description summary sentence. <a href="URL" style="color:#2563eb; text-decoration:none; font-size:12px; font-weight:600;">[來源連結]</a></li>]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Market (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES FROM PAST 24H IN ENGLISH. FORMAT EACH AS: <li style="margin-bottom:8px;"><strong>Headline Title</strong> — Description summary sentence. <a href="URL" style="color:#2563eb; text-decoration:none; font-size:12px; font-weight:600;">[Source Link]</a></li>]
            </ul>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:25px;">
            <div style="display:inline-block; background-color:#fef2f2; color:#991b1b; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">🧠 Artificial Intelligence & Tech</div>
            <img src="https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="AI Tech" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Tech Ecosystem (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TOP STORIES FROM PAST 24H IN TRADITIONAL CHINESE WITH HTML LINK HERE]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Innovation (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN ENGLISH BULLETS WITH HTML LINK HERE]
            </ul>
        </div>

        <div style="background-color:#ffffff; border-radius:8px; border:1px solid #e2e8f0; padding:20px; margin-bottom:15px;">
            <div style="display:inline-block; background-color:#eff6ff; color:#1e40af; font-size:12px; font-weight:700; padding:4px 8px; border-radius:4px; margin-bottom:10px; text-transform:uppercase;">📡 Wireless Communications (5G/6G)</div>
            <img src="https://images.unsplash.com/photo-1562408590-e32931084e23?auto=format&fit=crop&w=600&q=80" style="width:100%; height:140px; object-fit:cover; border-radius:6px; margin:8px 0 15px 0;" alt="Wireless Infrastructure" />
            
            <h4 style="margin:10px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇹🇼 Taiwan Telco Networks (繁體中文)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN TRADITIONAL CHINESE BULLETS WITH HTML LINK HERE]
            </ul>
            
            <h4 style="margin:20px 0 10px 0; font-size:15px; color:#334155; border-bottom:1px solid #f1f5f9; padding-bottom:4px;">🇺🇸 United States Infrastructure (English)</h4>
            <ul style="margin:0; padding-left:20px; font-size:14px; line-height:1.6; color:#334155;">
                [INSERT EXACTLY 3 CHOSEN ENGLISH BULLETS WITH HTML LINK HERE]
            </ul>
        </div>

    </div>

    CRITICAL INSTRUCTIONS:
    - Never break the shell layout template. Substitute placeholders with actual curated news facts from the source feed.
    - If the raw text discusses market pullbacks, tech crashes, or company news, report those exact specific events accurately. 
    - Language Enforcement: Taiwan content sections must be in native Traditional Chinese (繁體中文). USA sections and the Overview must be in English.
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
                
    return "<h2>Error: Gemini API remained unavailable after multiple retry attempts. Please run the script again.</h2>"

def send_resend_email(html_content):
    """Sends the curated intelligence newsletter using Resend API."""
    try:
        print("🚀 Requesting email delivery via Resend API securely...")
        params = {
            "from": "NewsEngine <onboarding@resend.dev>",
            "to": [RECIPIENT_EMAIL],
            "subject": "🌟 24-Hour Executive Strategic Curation Digest",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        print("✅ Success! 24-hour brief transferred to Resend successfully.")
    except Exception as e:
        print(f"❌ Resend API System Error: {e}")

def main():
    if "YOUR_" in NEWS_API_KEY or "YOUR_" in GEMINI_API_KEY or "YOUR_" in resend.api_key:
        print("❌ Configuration Missing.")
        return

    print("🛰️ Harvesting targeted, clean category arrays from past 24 hours...")
    master_feed = ""
    for category_name, query_string in CATEGORIES.items():
        master_feed += f"\n=== BATCH: {category_name.upper()} ===\n"
        master_feed += fetch_category_news(query_string) + "\n"
        
    print("🧠 Chief Editor Model: Extracting the top 3 highest-impact entries...")
    report_html = generate_expanded_matrix_html(master_feed)
    
    send_resend_email(report_html)

if __name__ == "__main__":
    main()