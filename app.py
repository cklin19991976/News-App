import os
import requests
import resend
from google import genai

# ==================== CONFIGURATION ====================
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "YOUR_NEWSAPI_ORG_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "your_account@gmail.com")

# Initialize the Resend API Key
resend.api_key = os.environ.get("RESEND_API_KEY", "YOUR_RESEND_API_KEY")

COUNTRIES = {
    "Taiwan": "taiwan",
    "United States": "usa OR america",
    "Ireland": "ireland"
}

TOPICS = (
    "(stock market OR finance OR \"artificial intelligence\" OR AI OR \"AI stocks\" OR "
    "\"Federal Reserve\" OR \"interest rate\" OR \"government bond\" OR Treasury OR "
    "wireless OR 5G OR 6G OR technology OR politics)"
)
# =======================================================

def fetch_targeted_news(country_query):
    """Fetches highly targeted articles to fulfill multi-bullet queries."""
    url = "https://newsapi.org/v2/everything"
    full_query = f"({country_query}) AND {TOPICS}"
    
    params = {
        "q": full_query,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 25,
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
    """Uses Gemini to organize articles by subject with exactly 3 items per country."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    You are an elite corporate intelligence brief compiler. Organize the raw global news logs provided below into a comprehensive HTML newsletter structured explicitly by SUBJECT/TOPIC.
    
    REQUIRED EMAIL STRUCTURE & QUANTITY RULES:
    1. Executive Overview (Written in English - max 3 sentences)
    
    2. Section 1: Stock Markets & Finance
       - FOCUS: AI-related stocks, broad market movements, US bonds, and Federal interest rate decisions.
       - COUNTRYSIDE BREAKDOWN: 
          * Under 'Taiwan' subheader, list EXACTLY 3 crisp news bullet items written in Traditional Chinese (繁體中文).
          * Under 'United States' subheader, list EXACTLY 3 crisp news bullet items written in English.
          * Under 'Ireland' subheader, list EXACTLY 3 crisp news bullet items written in English.
       - Image: <img src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="Finance Matrix" />
    
    3. Section 2: Artificial Intelligence & New Technology
       - FOCUS: Software models, computational hardware breakthrough architectures, and R&D.
       - COUNTRYSIDE BREAKDOWN: 
          * Under 'Taiwan' subheader, list EXACTLY 3 crisp news bullet items written in Traditional Chinese (繁體中文).
          * Under 'United States' subheader, list EXACTLY 3 crisp news bullet items written in English.
          * Under 'Ireland' subheader, list EXACTLY 3 crisp news bullet items written in English.
       - Image: <img src="https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="AI Tech Matrix" />
    
    4. Section 3: Wireless Communications (5G & 6G)
       - FOCUS: Next-gen 5G standalone networks, emerging 6G spectrum research, routers, telecom nodes, and mobile infrastructure.
       - COUNTRYSIDE BREAKDOWN: 
          * Under 'Taiwan' subheader, list EXACTLY 3 crisp news bullet items written in Traditional Chinese (繁體中文).
          * Under 'United States' subheader, list EXACTLY 3 crisp news bullet items written in English.
          * Under 'Ireland' subheader, list EXACTLY 3 crisp news bullet items written in English.
       - Image: <img src="https://images.unsplash.com/photo-1562408590-e32931084e23?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="Wireless Communication Matrix" />

    5. Section 4: Macro-Politics & Regulations
       - FOCUS: International relations, tech trade embargoes, legislative measures, and structural policies.
       - COUNTRYSIDE BREAKDOWN: 
          * Under 'Taiwan' subheader, list EXACTLY 3 crisp news bullet items written in Traditional Chinese (繁體中文).
          * Under 'United States' subheader, list EXACTLY 3 crisp news bullet items written in English.
          * Under 'Ireland' subheader, list EXACTLY 3 crisp news bullet items written in English.
       - Image: <img src="https://images.unsplash.com/photo-1590089415225-401ed6f9db8e?auto=format&fit=crop&w=600&q=80" style="max-width:100%; border-radius:6px; margin:10px 0;" alt="Macro Politics Matrix" />

    CRITICAL INSTRUCTIONS:
    - Language Enforcement: Taiwan content = Traditional Chinese (繁體中文). USA & Ireland content = English. Executive overview = English.
    - Keep each bullet point brief and high-level (maximum 2 sentences per bullet) to optimize payload limits.
    - Every bullet point MUST keep its live source link. Append HTML anchors to every item.
    - For English items use: <a href="URL" style="color:#3182ce; text-decoration:none; font-size:13px; margin-left:5px;">[Source Link]</a>
    - For Chinese items use: <a href="URL" style="color:#3182ce; text-decoration:none; font-size:13px; margin-left:5px;">[來源連結]</a>
    - Apply professional inline email CSS styling. Omit ```html markdown wrappers. Output only raw inner HTML.

    Raw data feed:
    {raw_news}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"<h2>Error creating intelligence report</h2><p>{e}</p>"

def send_resend_email(html_content):
    """Sends the intelligence report newsletter using Resend API."""
    try:
        print("🚀 Requesting email delivery via Resend API securely...")
        params = {
            "from": "NewsEngine <onboarding@resend.dev>",
            "to": [RECIPIENT_EMAIL],
            "subject": "📊 Complete Deep-Dive: Expanded Multi-Subject Intel Digest",
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

    print("🛰️ Mining intensive raw data array across global endpoints...")
    master_feed = ""
    for name, query in COUNTRIES.items():
        master_feed += f"\n=== {name.upper()} DATA INTERCEPT ===\n" + fetch_targeted_news(query) + "\n"
        
    print("🧠 Parsing deep multi-bullet language matrices and embedding web references...")
    report_html = generate_expanded_matrix_html(master_feed)
    
    send_resend_email(report_html)

if __name__ == "__main__":
    main()