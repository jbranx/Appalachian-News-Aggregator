"""
Daily News Aggregator
Fetches top news stories and creates an AI-powered summary email
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
    print("Fetching news...")
    params = {'country': 'us', 'pageSize': 10, 'apiKey': NEWS_API_KEY}
    try:
        response = requests.get("https://newsapi.org/v2/top-headlines", params=params, timeout=10)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        print(f"Found {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

def create_summary_with_claude(articles):
    print("Creating AI summary...")
    if not articles:
        return "<p>No news available today.</p>"
    
    articles_text = "\n\n".join([
        f"Title: {article.get('title', 'No title')}\nDescription: {article.get('description', 'No description')}\nSource: {article.get('source', {}).get('name', 'Unknown')}"
        for article in articles[:10]
    ])
    
    prompt = f"""Create a daily digest email from these top news stories:

{articles_text}

Please create a concise, engaging summary that:
1. Highlights the 5 most important stories
2. Provides a brief 2-3 sentence summary for each
3. Groups stories by topic
4. Uses a friendly tone
5. Formats as clean HTML"""
    
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
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px 20px; text-align: center; }}
        .content {{ padding: 30px 20px; }}
        .footer {{ background: #f5f5f5; padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Daily News Digest</h1>
        <p>{today}</p>
    </div>
    <div class="content">{summary_content}</div>
    <div class="footer">
        <p>Powered by AI</p>
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
        msg.attach(MIMEText(html_body, 'html'))
        
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
    print("DAILY NEWS AGGREGATOR STARTING")
    articles = fetch_news()
    if not articles:
        return
    summary = create_summary_with_claude(articles)
    html_email = create_html_email(summary)
    today = datetime.now().strftime("%B %d, %Y")
    send_email(f"Daily News - {today}", html_email)

if __name__ == "__main__":
    main()
