    #!/usr/bin/env python3
"""
Appalachian Daily News Aggregator
Daily email digest with Google Sheets subscriber management
Enhanced version with improved error handling and compliance
"""

import os
import sys
import logging
import feedparser
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
import html
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# === CONFIGURATION ===
SOURCES = [
    # Core Investigative & Policy
    {"name": "Kentucky Lantern", "url": "https://kentuckylantern.com/feed/"},
    {"name": "Cardinal News", "url": "https://cardinalnews.org/feed/"},
    {"name": "West Virginia Watch", "url": "https://www.wvwatch.org/feed/"},
    {"name": "Mountain State Spotlight", "url": "https://mountainstatespotlight.org/feed/"},
    {"name": "Ohio Valley ReSource", "url": "https://ohiovalleyresource.org/feed/"},
    # Regional Focus & Culture
    {"name": "Daily Yonder", "url": "https://dailyyonder.com/feed/"},
    {"name": "100 Days in Appalachia", "url": "https://www.100daysinappalachia.com/feed/"},
    {"name": "Appalachian Voices", "url": "https://appvoices.org/feed/"},
    {"name": "Scalawag Magazine", "url": "https://scalawagmagazine.org/feed/"},
    # Major Regional Papers
    {"name": "Charleston Gazette-Mail", "url": "https://www.wvgazettemail.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&c[]=news*&f=rss"},
    {"name": "Bristol Herald Courier", "url": "https://www.heraldcourier.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "Lexington Herald-Leader", "url": "https://www.kentucky.com/news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true"},
    # Local & Community
    {"name": "WYMT Mountain News", "url": "https://www.wymt.com/news/?format=rss"},
    {"name": "State Journal WV", "url": "https://www.wvnews.com/statejournal/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "WV Public Broadcasting", "url": "https://www.wvpublic.org/rss.xml"},
    # Environmental & Energy
    {"name": "Inside Climate News - Appalachia", "url": "https://insideclimatenews.org/category/appalachia/feed/"},
    {"name": "Southern Environmental Law Center", "url": "https://www.southernenvironment.org/feed/"},
    # Additional
    {"name": "Highlander Research", "url": "https://www.highlandercenter.org/feed/"},
    {"name": "West Virginia MetroNews", "url": "https://wvmetronews.com/feed/"},
    {"name": "Bluefield Daily Telegraph", "url": "https://www.bdtonline.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
]

TIME_WINDOW_HOURS = 72
MAX_PER_SOURCE = 20
MIN_STORIES_WARNING = 5

# === GET SUBSCRIBERS FROM GOOGLE SHEETS ===
def get_subscribers() -> List[str]:
    """Fetch active subscribers from Google Sheets with error handling"""
    try:
        log.info("Fetching subscribers from Google Sheets...")
        
        # Load credentials from environment variable
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        if not creds_json:
            log.error("GOOGLE_SHEETS_CREDENTIALS not found in environment")
            return []
        
        # Parse JSON credentials
        try:
            creds_dict = json.loads(creds_json)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse credentials JSON: {e}")
            return []
        
        # Create credentials with read-only scope
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        # Build Sheets API service
        service = build('sheets', 'v4', credentials=credentials)
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        
        if not sheet_id:
            log.error("GOOGLE_SHEET_ID not found in environment")
            return []
        
        # Read all rows from Sheet (skip header row)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range='Sheet1!A2:C1000'
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            log.warning("No data found in spreadsheet")
            return []
        
        # Filter for active subscribers
        # Column A = Email, Column C = Status
        subscribers = []
        for row in values:
            if len(row) >= 1:
                email = row[0].strip().lower()
                # Check status column (default to Active if empty)
                status = row[2].strip().lower() if len(row) >= 3 else "active"
                
                # Only include active subscribers with valid emails
                if status in ["active", ""] and email and '@' in email:
                    subscribers.append(email)
        
        log.info(f"✅ Found {len(subscribers)} active subscribers")
        return subscribers
        
    except Exception as e:
        log.error(f"❌ Failed to fetch subscribers from Google Sheets: {e}")
        log.error("Will attempt to send to fallback email only")
        return []

# === FETCH ARTICLES (unchanged from Grok's version) ===
def fetch_articles() -> List[Dict[str, Any]]:
    """Fetch articles from RSS feeds"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=TIME_WINDOW_HOURS)
    articles = []
    failed_sources = []

    log.info(f"Fetching articles from {len(SOURCES)} sources (last {TIME_WINDOW_HOURS} hours)...")

    for source in SOURCES:
        try:
            log.info(f"  → {source['name']}...")
            feed = feedparser.parse(source['url'])
            
            if not feed.entries:
                log.warning(f"    ✗ No entries from {source['name']}")
                failed_sources.append(source['name'])
                continue

            count = 0
            for entry in feed.entries[:MAX_PER_SOURCE]:
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                else:
                    try:
                        pub_date = date_parser.parse(entry.get("published") or entry.get("updated", ""))
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                    except:
                        pub_date = None

                if pub_date and pub_date >= cutoff:
                    title = html.escape(entry.title) if entry.title else "No title"
                    link = entry.link
                    summary = html.escape(entry.summary) if hasattr(entry, "summary") and entry.summary else ""

                    # Skip sports stories
                    lower_title = title.lower()
                    lower_summary = summary.lower()
                    sports_keywords = ["game", "score", "sports", "athletics", "team", "player", "coach", "ncaa", "high school football", "basketball", "baseball"]
                    if any(kw in lower_title or kw in lower_summary for kw in sports_keywords):
                        continue

                    articles.append({
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "source": source['name'],
                        "pub_date": pub_date.isoformat()
                    })
                    count += 1

            log.info(f"    ✓ {count} articles")
            
        except Exception as e:
            log.error(f"    ✗ Failed {source['name']}: {str(e)[:100]}")
            failed_sources.append(source['name'])

    articles.sort(key=lambda x: x['pub_date'], reverse=True)
    
    log.info(f"\n📊 Collection Summary:")
    log.info(f"   Total articles: {len(articles)}")
    log.info(f"   Failed sources: {len(failed_sources)}")
    
    if failed_sources:
        log.warning(f"   Sources with issues: {', '.join(failed_sources[:5])}")

    if len(articles) < MIN_STORIES_WARNING:
        log.warning(f"⚠️  Only {len(articles)} articles — below threshold of {MIN_STORIES_WARNING}")

    return articles[:40]

# === AI SUMMARIZATION (unchanged from Grok's version) ===
def generate_digest(articles: List[Dict]) -> str:
    """Generate digest using Claude AI"""
    log.info("🤖 Generating AI digest...")
    
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = "claude-sonnet-4-20250514"

    articles_data = ""
    for i, a in enumerate(articles, 1):
        articles_data += f"\n--- Article {i} ---\n"
        articles_data += f"Title: {a['title']}\n"
        articles_data += f"Link: {a['link']}\n"
        articles_data += f"Source: {a['source']}\n"
        articles_data += f"Summary: {a['summary'][:1000]}\n"

    prompt = f"""You are creating a daily news digest for Appalachian communities. Here are recent articles from trusted regional sources:

{articles_data}

Create a comprehensive, well-organized daily digest email using ONLY these HTML elements:
- <h2>Section Title</h2> for main categories
- <h3>Story Headline</h3> for individual stories
- <p>Content here</p> for all text paragraphs
- <a href="url">Link text</a> for article links
- <strong>text</strong> for emphasis

DO NOT use Markdown (no #, **, or ---). Only use HTML tags.

Organize stories into relevant categories such as:
- Economy & Jobs
- Energy & Environment  
- Health & Social Issues
- Education
- Politics & Policy
- Community & Culture
- Infrastructure & Development

IMPORTANT: Do NOT include any sports stories.

For each story:
1. Write a clear, engaging <h3> headline
2. Summarize in 2-3 sentences in a <p> tag
3. Include source and link: <p><strong>Source:</strong> <a href="url">Read more at SourceName</a></p>

Include AT LEAST 10-15 stories covering diverse topics. Focus on stories most important to Appalachian communities. Use a warm, community-focused tone. Start directly with <h2> tags."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        html_content = response.content[0].text.strip()
        log.info("✅ AI digest generated successfully")
        return html_content
        
    except Exception as e:
        log.error(f"❌ Claude API failed: {e}")
        raise

# === HTML EMAIL TEMPLATE ===
def build_email(html_content: str, article_count: int, recipient_email: str) -> str:
    """Build HTML email with proper footer and compliance"""
    today = datetime.now().strftime("%B %d, %Y")
    
    # Get signup form link from environment (with fallback)
    signup_link = os.getenv("GOOGLE_FORM_LINK", "https://jbranx.github.io/Appalachian-News-Aggregator")
    
    full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Appalachian Daily - {today}</title>
    <style>
        body {{ margin: 0; background: #f4f4f4; padding: 20px 0; font-family: Georgia, serif; }}
        .container {{ max-width: 650px; margin: 0 auto; background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #1e4620, #2d5016, #4a7c59); color: white; padding: 30px; text-align: center; }}
        .mountain {{ font-size: 42px; }}
        h1 {{ margin: 10px 0; font-size: 36px; font-weight: 300; }}
        .subtitle {{ margin: 5px 0; font-size: 18px; opacity: 0.9; }}
        .body {{ background: white; padding: 40px 35px; color: #2c3e50; line-height: 1.7; font-size: 16px; }}
        h2 {{ color: #2d5016; font-size: 24px; font-weight: 600; border-left: 5px solid #4a7c59; padding-left: 15px; margin: 35px 0 20px 0; }}
        h3 {{ color: #1e4620; font-size: 19px; margin: 25px 0 10px 0; }}
        p {{ margin: 10px 0; }}
        a {{ color: #2d5016; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .footer {{ background: #34495e; color: #ecf0f1; padding: 30px; text-align: center; font-size: 14px; }}
        .footer a {{ color: #ecf0f1; text-decoration: underline; }}
        .footer a:hover {{ color: #4a7c59; }}
        .subscribe-btn {{ background: #2d5016; color: white !important; padding: 10px 20px; text-decoration: none !important; border-radius: 5px; font-weight: 600; font-size: 16px; display: inline-block; margin: 10px 0; }}
        .subscribe-btn:hover {{ background: #1e4620; }}
        .unsubscribe {{ font-size: 12px; color: #bdc3c7; margin-top: 20px; }}
        @media (max-width: 600px) {{ .body {{ padding: 20px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="mountain">🏔️</div>
            <h1>Appalachian Daily</h1>
            <p class="subtitle">{today} • {article_count} stories</p>
        </div>
        <div class="body">
            {html_content}
        </div>
        <div class="footer">
            <p><strong>Curated from 21 trusted Appalachian news sources</strong></p>
            <p style="text-align: center; margin: 20px 0;">
                <a class="subscribe-btn" href="{signup_link}">Share with a Friend</a>
            </p>
            <p>
                <strong>Appalachian Daily</strong><br>
                Phoenix, Arizona<br>
                Created by Jim Branscome
            </p>
            <p>
                Questions or feedback? <a href="mailto:jbranscome@gmail.com">jbranscome@gmail.com</a>
            </p>
            <p class="unsubscribe">
                <a href="mailto:jbranscome@gmail.com?subject=Unsubscribe%20{recipient_email}&body=Please%20unsubscribe%20{recipient_email}">Unsubscribe</a> | 
                You're receiving this because you subscribed at Appalachian Daily
            </p>
            <p style="font-size: 11px; color: #95a5a6; margin-top: 15px;">
                <a href="https://github.com/jbranx/Appalachian-News-Aggregator">Powered by open-source automation</a>
            </p>
        </div>
    </div>
</body>
</html>'''
    return full_html

# === SEND EMAILS TO ALL SUBSCRIBERS ===
def send_to_subscribers(html_content: str, article_count: int):
    """Send digest to all active subscribers via Gmail SMTP"""
    
    # Get subscribers from Google Sheets
    subscribers = get_subscribers()
    
    # Fallback to owner email if no subscribers found
    if not subscribers:
        fallback_email = os.getenv("RECIPIENT_EMAIL")
        if fallback_email:
            log.warning(f"No subscribers found - sending test email to {fallback_email}")
            subscribers = [fallback_email]
        else:
            log.error("No subscribers and no fallback email configured")
            return
    
    # Get Gmail credentials
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not all([sender, password]):
        log.error("Missing Gmail credentials (EMAIL_ADDRESS or EMAIL_PASSWORD)")
        return
    
    today = datetime.now().strftime("%B %d, %Y")
    subject = f"🏔️ Appalachian Daily • {today}"
    
    success_count = 0
    fail_count = 0
    
    log.info(f"📧 Sending to {len(subscribers)} subscriber(s)...")
    
    # Connect to SMTP server once
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        
        # Send to each subscriber
        for recipient in subscribers:
            try:
                # Build personalized email
                email_html = build_email(html_content, article_count, recipient)
                
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"Appalachian Daily <{sender}>"
                msg["To"] = recipient
                
                part = MIMEText(email_html, "html", "utf-8")
                msg.attach(part)
                
                server.sendmail(sender, recipient, msg.as_string())
                success_count += 1
                log.info(f"  ✓ Sent to {recipient}")
                
            except Exception as e:
                fail_count += 1
                log.error(f"  ✗ Failed to send to {recipient}: {str(e)[:100]}")
        
        server.quit()
        
    except Exception as e:
        log.error(f"❌ SMTP connection failed: {e}")
        return
    
    log.info(f"\n📊 Email Summary:")
    log.info(f"   ✅ Sent successfully: {success_count}")
    log.info(f"   ❌ Failed: {fail_count}")

# === MAIN ===
def main():
    """Main execution"""
    log.info("\n" + "="*60)
    log.info("🏔️  APPALACHIAN DAILY NEWS AGGREGATOR")
    log.info("="*60 + "\n")

    # Fetch articles
    articles = fetch_articles()
    if len(articles) < 3:
        log.error("❌ Too few articles to proceed (minimum 3 required)")
        sys.exit(1)

    # Generate AI digest
    try:
        digest_html = generate_digest(articles)
    except Exception as e:
        log.error("❌ AI summarization failed - cannot proceed")
        sys.exit(1)

    # Count stories
    story_count = digest_html.count("<h3>")
    log.info(f"\n📰 Generated digest with {story_count} stories")
    
    # Send to all subscribers
    send_to_subscribers(digest_html, story_count)
    
    log.info("\n" + "="*60)
    log.info(f"✅ DIGEST COMPLETE: {story_count} stories sent")    
    log.info("="*60 + "\n")

if __name__ == "__main__":
    main()
