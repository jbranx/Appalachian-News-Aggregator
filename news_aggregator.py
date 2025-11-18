#!/usr/bin/env python3
"""
Appalachian Daily News Aggregator
Daily email digest of regional news using RSS + Claude AI
"""

import os
import sys
import logging
import feedparser
from datetime import datetime, timedelta, timezone
import json
import gspread
from google.oauth2.service_account import Credentials
from dateutil import parser as date_parser
import requests
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
import html


# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# === CONFIGURATION ===
SOURCES = [
    # ============================================
    # MULTI-STATE & REGIONAL COVERAGE
    # ============================================
    {"name": "Daily Yonder", "url": "https://dailyyonder.com/feed/"},
    {"name": "100 Days in Appalachia", "url": "https://www.100daysinappalachia.com/feed/"},
    {"name": "Ohio Valley ReSource", "url": "https://ohiovalleyresource.org/feed/"},
    {"name": "Appalachian Voices", "url": "https://appvoices.org/feed/"},
    {"name": "Scalawag Magazine", "url": "https://scalawagmagazine.org/feed/"},
    {"name": "Highlander Research", "url": "https://www.highlandercenter.org/feed/"},
    {"name": "Inside Climate News - Appalachia", "url": "https://insideclimatenews.org/category/appalachia/feed/"},
    {"name": "Southern Environmental Law Center", "url": "https://www.southernenvironment.org/feed/"},
    
    # ============================================
    # KENTUCKY
    # ============================================
    {"name": "Kentucky Lantern", "url": "https://kentuckylantern.com/feed/"},
    {"name": "WYMT Mountain News", "url": "https://www.wymt.com/news/?format=rss"},
    {"name": "Mountain Eagle", "url": "https://www.themountaineagle.com/feed/"},
    
    # ============================================
    # WEST VIRGINIA
    # ============================================
    {"name": "West Virginia Watch", "url": "https://www.wvwatch.org/feed/"},
    {"name": "Mountain State Spotlight", "url": "https://mountainstatespotlight.org/feed/"},
    {"name": "WV Public Broadcasting", "url": "https://www.wvpublic.org/rss.xml"},
    {"name": "West Virginia MetroNews", "url": "https://wvmetronews.com/feed/"},
    {"name": "Black By God West Virginia", "url": "https://blackbygod.com/feed/"},
    
    # ============================================
    # VIRGINIA
    # ============================================
    {"name": "Cardinal News", "url": "https://cardinalnews.org/feed/"},
    
    # ============================================
    # PENNSYLVANIA (Northern coalfields)
    # ============================================
    {"name": "PublicSource", "url": "https://www.publicsource.org/feed/"},
    {"name": "StateImpact Pennsylvania", "url": "https://stateimpact.npr.org/pennsylvania/feed/"},
    {"name": "PA Post", "url": "https://papost.org/feed/"},
    {"name": "Pittsburgh Current", "url": "https://pittsburghcurrent.com/feed/"},
    
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
    {"name": "Mountain Times", "url": "https://mountaintimes.com/feed/"},
    {"name": "Blue Ridge Public Radio", "url": "https://www.bpr.org/rss.xml"},
    
    # ============================================
    # SOUTH CAROLINA (Upstate ARC counties)
    # ============================================
    {"name": "The Nerve SC", "url": "https://thenerve.org/feed/"},
    
    # ============================================
    # GEORGIA (North Georgia ARC counties)
    # ============================================
    # Note: No non-paywall sources available - Rome News-Tribune is paywall
    
    # ============================================
    # ALABAMA (North Alabama ARC counties)
    # ============================================
    {"name": "AL.com", "url": "https://www.al.com/arc/outboundfeeds/rss/?outputType=xml"},
    
    # ============================================
    # MISSISSIPPI (Northeast MS ARC counties)
    # ============================================
    {"name": "Mississippi Today", "url": "https://mississippitoday.org/feed/"},
    
    # ============================================
    # OHIO (Southeast Ohio ARC counties)
    # ============================================
    {"name": "Athens News", "url": "https://www.athensnews.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
]

# === PAYWALL SOURCES (Subscription Required) ===
PAYWALL_SOURCES = [
    # Kentucky
    {"name": "Lexington Herald-Leader", "url": "https://www.kentucky.com/news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true"},
    
    # West Virginia
    {"name": "Charleston Gazette-Mail", "url": "https://www.wvgazettemail.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&c[]=news*&f=rss"},
    
    # Virginia
    {"name": "Bristol Herald Courier", "url": "https://www.heraldcourier.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "Roanoke Times", "url": "https://roanoke.com/search/?f=rss"},
    {"name": "Bluefield Daily Telegraph", "url": "https://www.bdtonline.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    
    # Tennessee
    {"name": "Johnson City Press", "url": "https://www.johnsoncitypress.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    {"name": "Knoxville News Sentinel", "url": "https://www.knoxnews.com/search/?f=rss"},
    
    # North Carolina
    {"name": "Asheville Citizen-Times", "url": "https://www.citizen-times.com/search/?f=rss"},
    
    # Georgia
    {"name": "Rome News-Tribune", "url": "https://www.northwestgeorgianews.com/rome/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss"},
    
    # Pennsylvania
    {"name": "Pittsburgh Post-Gazette", "url": "https://www.post-gazette.com/arc/outboundfeeds/rss/"},
]

TIME_WINDOW_HOURS = 72
MAX_PER_SOURCE = 20
MIN_STORIES_WARNING = 5

# === FETCH ARTICLES ===
def fetch_articles() -> tuple:
    """Fetch articles from both free and paywall sources"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=TIME_WINDOW_HOURS)
    
    def fetch_from_sources(sources, is_paywall=False):
        articles = []
        failed_sources = []
        
        for source in sources:
            try:
                log.info(f"Fetching {source['name']}...")
                feed = feedparser.parse(source['url'])
                if not feed.entries:
                    log.warning(f"No entries from {source['name']}")
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

                        # Skip sports
                        lower_title = title.lower()
                        lower_summary = summary.lower()
                        if any(kw in lower_title or kw in lower_summary for kw in ["game", "score", "sports", "athletics", "team", "player", "coach", "ncaa", "high school football"]):
                            continue

                        articles.append({
                            "title": title,
                            "link": link,
                            "summary": summary,
                            "source": source['name'],
                            "pub_date": pub_date.isoformat(),
                            "is_paywall": is_paywall
                        })
                        count += 1

                log.info(f"✓ {source['name']}: {count} articles")
            except Exception as e:
                log.error(f"✗ Failed {source['name']}: {e}")
                failed_sources.append(source['name'])
        
        if failed_sources:
            log.warning(f"Failed sources: {', '.join(failed_sources)}")
        
        return articles
    
    # Fetch from both source types
    free_articles = fetch_from_sources(SOURCES, is_paywall=False)
    paywall_articles = fetch_from_sources(PAYWALL_SOURCES, is_paywall=True)
    
    # Sort by date
    free_articles.sort(key=lambda x: x['pub_date'], reverse=True)
    paywall_articles.sort(key=lambda x: x['pub_date'], reverse=True)
    
    log.info(f"Total free articles: {len(free_articles)}")
    log.info(f"Total paywall articles: {len(paywall_articles)}")
    
    if len(free_articles) < MIN_STORIES_WARNING:
        log.warning(f"Only {len(free_articles)} free articles — below warning threshold")
    
    return free_articles[:40], paywall_articles[:20]

# === AI SUMMARIZATION ===
def generate_digest(free_articles: List[Dict], paywall_articles: List[Dict]) -> str:
    """Generate digest with separate free and paywall sections"""
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = "claude-sonnet-4-20250514"

    # Format free articles
    free_data = ""
    for i, a in enumerate(free_articles, 1):
        free_data += f"\n--- Article {i} ---\n"
        free_data += f"Title: {a['title']}\n"
        free_data += f"Link: {a['link']}\n"
        free_data += f"Source: {a['source']}\n"
        free_data += f"Summary: {a['summary'][:1000]}\n"
    
    # Format paywall articles
    paywall_data = ""
    for i, a in enumerate(paywall_articles, 1):
        paywall_data += f"\n--- Paywall Article {i} ---\n"
        paywall_data += f"Title: {a['title']}\n"
        paywall_data += f"Link: {a['link']}\n"
        paywall_data += f"Source: {a['source']}\n"
        paywall_data += f"Summary: {a['summary'][:1000]}\n"

    prompt = f"""You are creating a daily news digest for Appalachian communities. You have TWO types of articles:

=== FREE ACCESS ARTICLES ===
{free_data}

=== SUBSCRIPTION REQUIRED ARTICLES ===
{paywall_data}

Create a comprehensive daily digest email with TWO SECTIONS using ONLY these HTML elements:
- <h2>Section Title</h2> for main categories
- <h3>Story Headline</h3> for individual stories
- <p>Content here</p> for all text paragraphs
- <a href="url">Link text</a> for article links
- <strong>text</strong> for emphasis

DO NOT use Markdown (no #, **, or ---). Only use HTML tags.

SECTION 1: FREE ACCESS STORIES
Organize these stories into relevant categories such as:
- Economy & Jobs
- Energy & Environment  
- Health & Social Issues
- Education
- Politics & Policy
- Community & Culture
- Infrastructure & Broadband

SECTION 2: PREMIUM SOURCES (Subscription Required)
After all free stories, add this exact heading:
<h2 style="color: #8B4513; border-left-color: #8B4513;">📰 Premium Sources (Subscription Required)</h2>
<p style="color: #666; font-style: italic; margin-bottom: 20px;">The following stories require paid subscriptions but may be of interest to our readers:</p>

Then list paywall stories with the 🔒 emoji in each headline like this:
<h3>🔒 Story Headline Here</h3>

IMPORTANT: Do NOT include any sports stories from either section. Skip all articles about sports, athletics, games, or sporting events.

For each story:
1. Write a clear, engaging <h3> headline
2. Summarize in 2-3 sentences in a <p> tag
3. Include source and link: <p><strong>Source:</strong> <a href="link">Read more at source_name</a></p>

Include AT LEAST 15 free stories and 8-10 paywall stories. Use a warm, community-focused tone. Start directly with <h2> tags for the first free category.
"""

    try:
        log.info("Sending to Claude AI...")
        response = client.messages.create(
            model=model,
            max_tokens=5000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        html_content = response.content[0].text.strip()
        log.info("AI digest generated with paywall section.")
        return html_content
    except Exception as e:
        log.error(f"Claude API failed: {e}")
        raise

# === HTML EMAIL TEMPLATE ===
def build_email(html_content: str, article_count: int) -> str:
    today = datetime.now().strftime("%B %d, %Y")
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
        .footer a {{ color: #ecf0f1; }}
        .subscribe-btn {{ background: #2d5016; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: 600; font-size: 16px; display: inline-block; margin: 10px 0; }}
        .subscribe-btn:hover {{ background: #1e4620; }}
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
            <p>Curated from 40+ trusted Appalachian news sources.</p>
            <p style="text-align: center; margin: 20px 0;">
                <a class="subscribe-btn" href="https://jbranx.github.io/Appalachian-News-Aggregator">Subscribe for Daily Updates</a>
            </p>
           <p>Appalachian Daily is a news aggregator created by Jim Branscome. You can provide him feedback at <a href="mailto:jbranscome@gmail.com">jbranscome@gmail.com</a>.</p>
            <p><a href="https://github.com/jbranx/Appalachian-News-Aggregator">Powered by open-source automation</a></p>
        </div>
        </div>
    </div>
</body>
</html>'''
    return full_html

# === GOOGLE SHEETS & EMAIL ===
def get_subscribers():
    """Read subscriber emails from Google Sheet"""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        
        if not creds_json:
            print("⚠️ No Google Sheets credentials - using fallback email")
            return [os.environ.get('RECIPIENT_EMAIL', '')]
        
        creds_dict = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        
        sheet = client.open_by_key("12n0VY54S1jjl-KBrL7O_BID_Q90jidifJ_LthmwDYVk").sheet1
        records = sheet.get_all_records()
        
        subscribers = []
        for record in records:
            email = record.get('Email Address', '').strip()
            if email and '@' in email:
                subscribers.append(email)
        
        print(f"✅ Found {len(subscribers)} subscribers")
        return subscribers
        
    except Exception as e:
        print(f"❌ Error reading Google Sheets: {e}")
        return [os.environ.get('RECIPIENT_EMAIL', '')]


def send_to_subscribers(html_content, subject="Appalachian Daily Digest"):
    """Send email to all subscribers"""
    subscribers = get_subscribers()
    
    if not subscribers:
        print("⚠️ No subscribers found")
        return
    
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = os.environ['EMAIL_ADDRESS']
    sender_password = os.environ['EMAIL_PASSWORD']
    
    success_count = 0
    fail_count = 0
    
    for recipient in subscribers:
        try:
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = f"Appalachian Daily <{sender_email}>"
            message['To'] = recipient
            
            unsubscribe_url = "https://docs.google.com/forms/d/e/1FAIpQLSeqq0YbOTAI0bz0PbzTSbUBbK2usl2E0GDUo9glISXueAdfXg/viewform"
            html_with_unsub = html_content.replace(
                '</body>',
                f'<div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">'
                f'<a href="{unsubscribe_url}" style="color: #2d5016;">Unsubscribe</a> | '
                f'Appalachian Daily Newsletter</div></body>'
            )
            
            html_part = MIMEText(html_with_unsub, 'html')
            message.attach(html_part)
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(message)
            
            success_count += 1
            print(f"✅ Sent to {recipient}")
            
        except Exception as e:
            fail_count += 1
            print(f"❌ Failed to send to {recipient}: {e}")
    
    print(f"\n📊 Results: {success_count} sent, {fail_count} failed")


# === MAIN ===
def main():
    log.info("Starting Appalachian Daily News Aggregator")

    free_articles, paywall_articles = fetch_articles()
    if len(free_articles) < 3:
        log.error("Too few articles to proceed.")
        sys.exit(1)
    try:
        digest_html = generate_digest(free_articles, paywall_articles)
    except Exception as e:
        log.error(f"AI summarization failed: {e}")
        sys.exit(1)
    story_count = digest_html.count("<h3>")
    email_html = build_email(digest_html, story_count)
    send_to_subscribers(email_html)
    log.info(f"Digest complete: {story_count} stories")

if __name__ == "__main__":
    main()
