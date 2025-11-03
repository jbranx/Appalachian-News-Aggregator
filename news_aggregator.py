
"""
Appalachian News Aggregator
Fetches Appalachian region news and creates an AI-powered summary email
"""

import os
import requests
from datetime import datetime
from anthropic import Anthropic

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')

def fetch_news():
    print("Fetching Appalachian news...")
    
    params = {
        'q': 'Appalachia OR "West Virginia" OR Kentucky OR Tennessee OR "North Carolina" OR Virginia OR "Appalachian region"',
        'language': 'en',
        'pageSize': 20,
        'sortBy': 'publishedAt',
        'apiKey': NEWS_API_KEY
    }
    
    try:
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        articles = response.json().get('articles', [])
        print(f"Found {len(articles)} Appalachian articles")
        return articles
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

def create_summary_with_claude(articles):
    print("Creating AI summary...")
    if not articles:
        return "<p>No Appalachian news available today.</p>"
    
    articles_text = "\n\n".join([
        f"Title: {article.get('title', 'No title')}\nDescription: {article.get('description', 'No description')}\nSource: {article.get('source', {}).get('name', 'Unknown')}"
        for article in articles[:15]
    ])
    
    prompt = f"""Create a daily digest email from these Appalachian region news stories:

{articles_text}

CRITICAL: You must respond with ONLY valid HTML code. Do NOT use Markdown syntax.

Use these HTML tags ONLY:
- <h2> for main section headings (like "Regional Economy", "Local Politics")
- <h3> for individual story titles
- <p> for all paragraph text
- <strong> for bold emphasis
- <br> for line breaks

Do NOT use: # symbols, ** for bold, --- for dividers, or any Markdown

Create a well-formatted digest that:
1. Groups stories by topic using <h2>Topic Name</h2>
2. For each story: <h3>Story Title</h3> followed by <p>2-3 sentence summary</p>
3. Focuses on Appalachian region relevance
4. Uses a warm, community-focused tone

Start directly with <h2> tags, no intro text."""
    
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        print("Summary created")
        return message.content[0].text
    except Exception as e:
        print(f"Error creating summary: {e}")
        return f"<p>Error: {str(e)}</p>"

def create_html_email(summary_content):
    today = datetime.now().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Georgia, serif; line-height: 1.8; color: #333; background: #f9f9f9; }}
        .container {{ max-width: 700px; margin: 0 auto; background: white; }}
        .header {{ background: linear-gradient(135deg, #2d5016, #4a7c59); color: white; padding: 40px 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 32px; font-weight: normal; }}
        .header p {{ margin: 10px 0 0 0; font-size: 16px; opacity: 0.9; }}
        .content {{ padding: 40px 30px; }}
        .content h2 {{ color: #2d5016; border-bottom: 2px solid #4a7c59; padding-bottom: 10px; margin-top: 30px; }}
        .content h3 {{ color: #333; margin-top: 20px; margin-bottom: 10px; }}
        .content p {{ margin: 10px 0; }}
        .footer {{ background: #f5f5f5; padding: 30px; text-align: center; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏔️ Appalachian News Daily</h1>
            <p>{today}</p>
        </div>
        <div class="content">
            {summary_content}
        </div>
        <div class="footer">
            <p>Your daily digest of Appalachian region news</p>
            <p>Powered by AI | Delivered with 💚</p>
        </div>
    </div>
</body>
</html>"""

def send_email(subject, html_body):
    print("Sending email...")
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def main():
    print("APPALACHIAN NEWS AGGREGATOR STARTING")
    articles = fetch_news()
    if not articles:
        print("No articles found")
        return
    summary = create_summary_with_claude(articles)
    html_email = create_html_email(summary)
    today = datetime.now().strftime("%B %d, %Y")
    send_email(f"Appalachian News - {today}", html_email)

if __name__ == "__main__":
    main()
