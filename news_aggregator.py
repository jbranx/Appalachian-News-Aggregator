#!/usr/bin/env python3
"""
Appalachian Daily News Aggregator
Fetches news from RSS feeds across the 13-state Appalachian region,
uses Claude to generate a curated digest, and emails it to subscribers.
"""

import os
import json
import smtplib
import feedparser
import anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# ============================================
# FREE / ACCESSIBLE SOURCES (34 sources)
# ============================================
SOURCES = [
    # ============================================
    # MULTI-STATE & REGIONAL COVERAGE
    # ============================================
    {"name": "Daily Yonder", "url": "https://dailyyonder.com/feed/"},
    {"name": "100 Days in Appalachia", "url": "https://www.100daysinappalachia.com/feed/"},
    {"name": "Ohio Valley ReSource", "url": "https://ohiovalleyresource.org/feed/"},
    {"name": "Appalachian Voices", "url": "https://appvoices.org/feed/"},
    {"name": "Scalawag Magazine", "url": "https://scalawagmagazine.org/feed/"},
    {"name": "Inside Climate News - Appalachia", "url": "https://insideclimatenews.org/category/appalachia/feed/"},
    
    # ============================================
    # KENTUCKY
    # ============================================
    {"name": "Kentucky Lantern", "url": "https://kentuckylantern.com/feed/"},
    {"name": "WYMT Mountain News", "url": "https://www.wymt.com/news/?format=rss"},
    {"name": "Mountain Eagle", "url": "https://www.themountaineagle.com/feed/"},
    {"name": "Louisville Public Media", "url": "https://www.lpm.org/rss.xml"},
    {"name": "WEKU Eastern Kentucky", "url": "https://www.weku.org/rss.xml"},
    {"name": "Harlan Enterprise", "url": "https://harlanenterprise.net/feed/"},
    
    # ============================================
    # WEST VIRGINIA
    # ============================================
    {"name": "West Virginia Watch", "url": "https://westvirginiawatch.com/feed/"},
    {"name": "Mountain State Spotlight", "url": "https://mountainstatespotlight.org/feed/"},
    {"name": "WV Public Broadcasting", "url": "https://www.wvpublic.org/rss.xml"},
    {"name": "West Virginia MetroNews", "url": "https://wvmetronews.com/feed/"},
    
    # ============================================
    # VIRGINIA
    # ============================================
    {"name": "Cardinal News", "url": "https://cardinalnews.org/feed/"},
    {"name": "Coalfield Progress", "url": "https://www.thecoalfieldprogress.com/feed/"},
    
    # ============================================
    # TENNESSEE
    # ============================================
    {"name": "Tennessee Lookout", "url": "https://tennesseelookout.com/feed/"},
    {"name": "WJHL News", "url": "https://www.wjhl.com/feed/"},
    
    # ============================================
    # NORTH CAROLINA
    # ============================================
    {"name": "Carolina Public Press", "url": "https://carolinapublicpress.org/feed/"},
    {"name": "Smoky Mountain News", "url": "https://smokymountainnews.com/feed/"},
    {"name": "NC Health News", "url": "https://www.northcarolinahealthnews.org/feed/"},
    {"name": "Blue Ridge Public Radio", "url": "https://www.bpr.org/rss.xml"},
    
    # ============================================
    # PENNSYLVANIA
    # ============================================
    {"name": "PublicSource", "url": "https://www.publicsource.org/feed/"},
    {"name": "StateImpact Pennsylvania", "url": "https://stateimpact.npr.org/pennsylvania/feed/"},
    
    # ============================================
    # ALABAMA (North Alabama ARC counties)
    # ============================================
    {"name": "AL.com", "url": "https://www.al.com/arc/outboundfeeds/rss/?outputType=xml"},
    
    # ============================================
    # MISSISSIPPI (Northeast MS ARC counties)
    # ============================================
    {"name": "Mississippi Today", "url": "https://mississippitoday.org/feed/"},
    
    # ============================================
    # GEORGIA (North Georgia ARC counties)
    # ============================================
    {"name": "Georgia Recorder", "url": "https://georgiarecorder.com/feed/"},
    
    # ============================================
    # SOUTH CAROLINA (Upstate ARC counties)
    # ============================================
    {"name": "SC Daily Gazette", "url": "https://scdailygazette.com/feed/"},
    
    # ============================================
    # OHIO (Southeast Ohio ARC counties)
    # ============================================
    {"name": "Ohio Capital Journal", "url": "https://ohiocapitaljournal.com/feed/"},
    
    # ============================================
    # NEW YORK (Southern Tier ARC counties)
    # ============================================
    {"name": "NY Focus", "url": "https://www.nysfocus.com/feed/"},
    
    # ============================================
    # MARYLAND (Western MD ARC counties)
    # ============================================
    {"name": "Maryland Matters", "url": "https://www.marylandmatters.org/feed/"},
]

# ============================================
# PAYWALL / SUBSCRIPTION SOURCES (10 sources)
# ============================================
PAYWALL_SOURCES = [
    # Kentucky
    {"name": "Lexington Herald-Leader", "url": "https://www.kentucky.com/news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true"},
    
    # West Virginia
    {"name": "Charleston Gazette-Mail", "url": "https://www.wvgazettemail.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&c[]=news*&f=rss"},
    
    # Virginia
    {"name": "Bristol Herald Courier", "url": "https://www.heraldcourier.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "Roanoke Times", "url": "https://roanoke.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "Bluefield Daily Telegraph", "url": "https://www.bdtonline.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    
    # Tennessee
    {"name": "Johnson City Press", "url": "https://www.johnsoncitypress.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "Knoxville News Sentinel", "url": "https://www.knoxnews.com/news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true"},
    
    # North Carolina
    {"name": "Asheville Citizen-Times", "url": "https://www.citizen-times.com/news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true"},
    
    # Georgia
    {"name": "Rome News-Tribune", "url": "https://www.northwestgeorgianews.com/rome/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    
    # Pennsylvania
    {"name": "Pittsburgh Post-Gazette", "url": "https://www.post-gazette.com/rss/headlines-news"},
]

# Configuration
TIME_WINDOW_HOURS = 72
MAX_ARTICLES_PER_SOURCE = 20

def fetch_articles() -> Tuple[List[Dict], List[Dict]]:
    """Fetch articles from all RSS feeds within the time window."""
    cutoff = datetime.now() - timedelta(hours=TIME_WINDOW_HOURS)
    free_articles = []
    paywall_articles = []
    
    # Fetch from free sources
    for source in SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            count = 0
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                try:
                    # Try to get published date
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    else:
                        pub_date = datetime.now()
                    
                    if pub_date >= cutoff:
                        free_articles.append({
                            "source": source["name"],
                            "title": entry.get("title", "Untitled"),
                            "link": entry.get("link", ""),
                            "summary": entry.get("summary", entry.get("description", ""))[:500],
                            "date": pub_date.strftime("%Y-%m-%d %H:%M")
                        })
                        count += 1
                except Exception as e:
                    logger.warning(f"Error parsing entry from {source['name']}: {e}")
                    continue
            logger.info(f"✓ {source['name']}: {count} articles")
        except Exception as e:
            logger.error(f"✗ {source['name']}: {e}")
    
    # Fetch from paywall sources
    for source in PAYWALL_SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            count = 0
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    else:
                        pub_date = datetime.now()
                    
                    if pub_date >= cutoff:
                        paywall_articles.append({
                            "source": source["name"],
                            "title": entry.get("title", "Untitled"),
                            "link": entry.get("link", ""),
                            "summary": entry.get("summary", entry.get("description", ""))[:500],
                            "date": pub_date.strftime("%Y-%m-%d %H:%M"),
                            "paywall": True
                        })
                        count += 1
                except Exception as e:
                    logger.warning(f"Error parsing entry from {source['name']}: {e}")
                    continue
            logger.info(f"✓ [PAYWALL] {source['name']}: {count} articles")
        except Exception as e:
            logger.error(f"✗ [PAYWALL] {source['name']}: {e}")
    
    logger.info(f"Total free articles: {len(free_articles)}")
    logger.info(f"Total paywall articles: {len(paywall_articles)}")
    
    return free_articles, paywall_articles

def generate_digest(free_articles: List[Dict], paywall_articles: List[Dict]) -> str:
    """Use Claude to generate a curated news digest."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    
    # Prepare article data for Claude
    free_articles_text = json.dumps(free_articles, indent=2)
    paywall_articles_text = json.dumps(paywall_articles, indent=2) if paywall_articles else "[]"
    
    prompt = f"""You are an expert Appalachian news curator. Your job is to create a compelling daily news digest 
from the following articles gathered from news sources across the 13-state Appalachian region.

FREE/ACCESSIBLE ARTICLES:
{free_articles_text}

PAYWALL/SUBSCRIPTION ARTICLES:
{paywall_articles_text}

Please create a news digest following these rules:

1. SELECT the most important and interesting stories (aim for 15-25 total from free sources, plus any relevant paywall stories)
2. EXCLUDE: Sports scores/games, weather forecasts, obituaries, event calendars, crime blotter items, and stories not relevant to Appalachia
3. PRIORITIZE: Economic development, policy/politics, environment, energy/coal, healthcare, education, culture, and community stories
4. GROUP stories by theme or topic (e.g., "Energy & Environment", "Economic Development", "Health & Healthcare", etc.)
5. For each story, provide:
   - A compelling headline (can be edited for clarity)
   - The source name
   - A 1-2 sentence summary
   - The link

FORMAT YOUR RESPONSE AS HTML with this structure:

<h2>🏔️ [Theme Name]</h2>
<div class="story">
<h3><a href="[link]">[Headline]</a></h3>
<p class="source">[Source Name]</p>
<p class="summary">[Your 1-2 sentence summary]</p>
</div>

[Repeat for each story in this theme]

After all free source stories, if there are paywall articles, add a section:

<h2>📰 Premium Sources (Subscription Required)</h2>
<p class="premium-note">The following stories are from subscription-based publications. Links may require a subscription to access.</p>
[Include paywall stories with 🔒 icon before headline]

If no paywall articles are relevant or available, you can skip the Premium Sources section entirely.

Make the digest engaging and informative. Focus on stories that matter to people living in and caring about Appalachia."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except anthropic.APIError as e:
            logger.warning(f"API attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

def build_email(digest: str) -> str:
    """Build the complete HTML email."""
    today = datetime.now().strftime("%B %d, %Y")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Appalachian Daily News - {today}</title>
    <style>
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            line-height: 1.6;
            max-width: 700px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 30px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #2c5530;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #2c5530;
            margin: 0;
            font-size: 28px;
        }}
        .header .date {{
            color: #666;
            font-style: italic;
            margin-top: 5px;
        }}
        h2 {{
            color: #2c5530;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        .story {{
            margin-bottom: 25px;
            padding-left: 15px;
            border-left: 3px solid #e0e0e0;
        }}
        .story h3 {{
            margin: 0 0 5px 0;
            font-size: 18px;
        }}
        .story h3 a {{
            color: #1a5276;
            text-decoration: none;
        }}
        .story h3 a:hover {{
            text-decoration: underline;
        }}
        .source {{
            color: #888;
            font-size: 14px;
            margin: 5px 0;
            font-style: italic;
        }}
        .summary {{
            color: #333;
            margin: 10px 0 0 0;
        }}
        .premium-note {{
            background-color: #fff9e6;
            padding: 10px;
            border-radius: 5px;
            font-size: 14px;
            color: #856404;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 14px;
            color: #666;
        }}
        .footer a {{
            color: #2c5530;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏔️ Appalachian Daily News</h1>
            <div class="date">{today}</div>
        </div>
        
        {digest}
        
       <div class="footer">
            <p>Curated from 40+ trusted Appalachian news sources across the 13-state region.</p>
            <p>Questions or feedback? Reply to this email.</p>
            <p>📬 Know someone who should read this? <a href="https://jbranx.github.io/Appalachian-News-Aggregator/">Share this link</a> so they can subscribe.</p>
            <p><a href="https://docs.google.com/forms/d/e/1FAIpQLSeqq0YbOTAI0bz0PbzTSbUBbK2usl2E0GDUo9glISXueAdfXg/viewform">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>"""
    
    return html
def get_subscribers() -> List[str]:
    """Get subscriber list from Google Sheets."""
    try:
        # Load credentials from environment variable
        creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        if not creds_json:
            logger.warning("No Google Sheets credentials found, using fallback email")
            return [os.environ.get("RECIPIENT_EMAIL", "jbranscome@gmail.com")]
        
        creds_dict = json.loads(creds_json)
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly'
        ]
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        
        # Open the spreadsheet by ID
        sheet_id = "12n0VY54S1jjl-KBrL7O_BID_Q90jidifJ_LthmwDYVk"
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        
        # Get all email addresses from column A (skip header)
        emails = worksheet.col_values(2)[1:]
        
        # Filter out empty cells and validate emails
        valid_emails = [email.strip() for email in emails if email and "@" in email]
        
        logger.info(f"Found {len(valid_emails)} subscribers")
        return valid_emails
        
    except Exception as e:
        logger.error(f"Error accessing Google Sheets: {e}")
        return [os.environ.get("RECIPIENT_EMAIL", "jbranscome@gmail.com")]

def send_email(html_content: str, recipients: List[str]):
    """Send the newsletter via Gmail SMTP."""
    sender_email = os.environ["EMAIL_ADDRESS"]
    sender_password = os.environ["EMAIL_PASSWORD"]
    
    today = datetime.now().strftime("%B %d, %Y")
    subject = f"Appalachian Daily News - {today}"
    
    for recipient in recipients:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"Appalachian Daily News <{sender_email}>"
            msg['To'] = recipient
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient, msg.as_string())
            
            logger.info(f"✓ Sent to {recipient}")
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            logger.error(f"✗ Failed to send to {recipient}: {e}")

def main():
    """Main function to run the news aggregator."""
    logger.info("Starting Appalachian Daily News aggregator...")
    
    # Fetch articles from both free and paywall sources
    free_articles, paywall_articles = fetch_articles()
    
    if not free_articles and not paywall_articles:
        logger.warning("No articles found. Exiting.")
        return
    
    # Generate digest with Claude
    logger.info("Generating digest with Claude...")
    digest = generate_digest(free_articles, paywall_articles)
    
    # Build email
    html_email = build_email(digest)
    
    # Get subscribers and send
    subscribers = get_subscribers()
    logger.info(f"Sending to {len(subscribers)} subscribers...")
    send_email(html_email, subscribers)
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
