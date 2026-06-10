import os
import time
import requests
import resend
from google import genai
from google.genai import types # 🛠️ Imported to control the thinking configuration

# ==================== CONFIGURATION ====================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "YOUR_NEWSAPI_ORG_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "your_account@gmail.com")

# Initialize the Resend API Key
resend.api_key = os.environ.get("RESEND_API_KEY", "YOUR_RESEND_API_KEY")

COUNTRIES = {
    "Taiwan": "taiwan",
    "United States": "usa OR america"
}

TOPICS = (
    "(stock market OR finance OR \"artificial intelligence\" OR AI OR \"AI stocks\" OR "
    "\"Federal Reserve\" OR \"interest rate\" OR \"government bond\" OR Treasury OR "
    "wireless OR 5G OR 6G OR technology)"
)
# =======================================================

def fetch_targeted_news(country_query):
    """Fetches a broad news array to provide Gemini with a rich pool for editorial curation."""
    url = "https://newsapi.org/v2/everything"
    full_query = f"({country_query}) AND {TOPICS}"
    
    params = {
        "q": full_query,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 45,        
        "apiKey": NEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        formatted_news = []
        
        for art in articles:
            title = art.get("title", "No Title")
            source = art.get("source", {}).get("name", "Unknown")
            description = art.get("description", "")
            article_url = art.get("url", "#")
            
            if title != "[Removed]":
                formatted_news.append(
                    f"- [{source}] {title}\n"
                    f"  Link: {article_url}\n"
                    f"  Snippet: {description}"
                )
                
        return "\n\n".join(formatted_news) if formatted_news else "No matching records."
    except Exception as e:
        return f"Error: {e}"

def generate_expanded_matrix_html(raw_news):
    """Uses optimized Gemini models to map daily news matrices without triggering rate limit blocks."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are an elite chief corporate intelligence officer. Analyze the raw recent data feed provided below. Your primary task is to critically evaluate all entries and CHOOSE ONLY the absolute most important, high-impact, and critical news stories of the day for each subject matrix. Ignore minor updates; prioritize structural shifts, major market movements, macro policy updates, and breakthrough announcements.
    
    REQUIRED EMAIL STRUCTURE & EDITORIAL RULES:
    1. Executive Overview (Written in English - max 3 sentences summarizing the single most critical global development across your sectors today).
    
    2. Section 1: Stock Markets & Finance
       - SELECTION CRITERIA: Evaluate and choose the top 3 most critical macro-financial updates regarding AI-related stocks, broad indexes, Treasuries, and Fed interest rate trajectories.
       - GEOGRAPHICAL BREAKDOWN:
          * Under a 'Taiwan' subheader, list EXACTLY 3 chosen top-tier news items written in Traditional Chinese (繁體中文).
          * Under a 'United States' subheader, list EXACTLY 3 chosen top-tier news items written in English.
       - Section Image: <img src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="Finance Matrix" />
    
    3. Section 2: Artificial Intelligence & New Technology
       - SELECTION CRITERIA: Evaluate and choose the top 3 most groundbreaking updates regarding foundational software architectures, infrastructure hardware breakthroughs, or monumental corporate integrations.
       - GEOGRAPHICAL BREAKDOWN:
          * Under a 'Taiwan' subheader, list EXACTLY 3 chosen top-tier news items written in Traditional Chinese (繁體中文).
          * Under a 'United States' subheader, list EXACTLY 3 chosen top-tier news items written in English.
       - Section Image: <img src="https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="AI Tech Matrix" />
    
    4. Section 3: Wireless Communications (5G & 6G)
       - SELECTION CRITERIA: Evaluate and choose the top 3 most vital infrastructure developments across 5G Advanced deployments, 6G research, spectral management, or tier-1 carrier announcements.
       - GEOGRAPHICAL BREAKDOWN:
          * Under a 'Taiwan' subheader, list EXACTLY 3 chosen top-tier news items written in Traditional Chinese (繁體中文).
          * Under a 'United States' subheader, list EXACTLY 3 chosen top-tier news items written in English.
       - Section Image: <img src="https://images.unsplash.com/photo-1562408590-e32931084e23?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="Wireless Communication Matrix" />

    CRITICAL EXECUTION RULES:
    - Language Enforcement: Taiwan sections must be in native Traditional Chinese (繁體中文). USA sections and the Overview must be in English.
    - Each bullet item must be concise (max 2 sentences), focusing exclusively on *why* this news is the most critical event of the day.
    - Every bullet point must retain its original source link via a clean HTML anchor tag.
    - For English items use: <a href="URL" style="color:#3182ce; text-decoration:none; font-size:13px; margin-left:5px;">[Source Link]</a>
    - For Chinese items use: <a href="URL" style="color:#3182ce; text-decoration:none; font-size:13px; margin-left:5px;">[來源連結]</a>
    - Apply professional inline email CSS styling. Omit all ```html wrappers. Output only raw inner HTML.

    Raw daily data pool:
    {raw_news}
    """
    
    max_retries = 3
    delay = 5  
    
    # 🛠️ Configuration to clear out slow internal model thinking steps to maximize free-tier API speed
    api_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    
    for attempt in range(max_retries):
        try:
            # 🛠️ Switched to the high-throughput 'gemini-2.5-flash-lite' model
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
    """Sends the curated intelligence newsletter using Resend API to bypass SMTP firewalls."""
    try:
        print("🚀 Requesting email delivery via Resend API securely...")
        params = {
            "from": "NewsEngine <onboarding@resend.dev>",
            "to": [RECIPIENT_EMAIL],
            "subject": "🌟 Top-Tier Strategic Curation: Daily Executive News Briefing",
            "html": html_content,
        }
        
        resend.Emails.send(params)
        print("✅ Success! Email transferred to Resend API pipeline successfully.")
    except Exception as e:
        print(f"❌ Resend API System Error: {e}")

def main():
    if "YOUR_" in NEWS_API_KEY or "YOUR_" in GEMINI_API_KEY or "YOUR_" in resend.api_key:
        print("❌ Configuration Missing.")
        return

    print("🛰️ Mining broad raw data pool across selected endpoints...")
    master_feed = ""
    for name, query in COUNTRIES.items():
        master_feed += f"\n=== {name.upper()} DATA INTERCEPT ===\n" + fetch_targeted_news(query) + "\n"
        
    print("🧠 Chief Editor Model: Evaluating raw feeds to filter, weigh, and select today's top stories...")
    report_html = generate_expanded_matrix_html(master_feed)
    
    send_resend_email(report_html)

if __name__ == "__main__":
    main()