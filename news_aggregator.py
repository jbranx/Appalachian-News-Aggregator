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
from dateutil import parser as date_parser
import requests
from anthropic import Anthropic
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
import html
import hashlib
import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# === FETCH ARTICLES ===
def fetch_articles() -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=TIME_WINDOW_HOURS)
    articles = []
    failed_sources = []

    for source in SOURCES:
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
                        "pub_date": pub_date.isoformat()
                    })
                    count += 1

            log.info(f"✓ {source['name']}: {count} articles")
        except Exception as e:
            log.error(f"✗ Failed {source['name']}: {e}")
            failed_sources.append(source['name'])

    articles.sort(key=lambda x: x['pub_date'], reverse=True)
    log.info(f"Total articles collected: {len(articles)}")
    if failed_sources:
        log.warning(f"Failed sources: {', '.join(failed_sources)}")

    if len(articles) < MIN_STORIES_WARNING:
        log.warning(f"Only {len(articles)} articles — below warning threshold")

    return articles[:40]  # Top 40 for AI selection

# === AI SUMMARIZATION ===
def generate_digest(articles: List[Dict]) -> str:
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

IMPORTANT: Do NOT include any sports stories. Skip all articles about sports, athletics, games, or sporting events.

For each story:
1. Write a clear, engaging <h3> headline
2. Summarize in 2-3 sentences in a <p> tag
3. Include source and link: <p><strong>Source:</strong> <a href="{a['link']}">Read more at {a['source']}</a></p>

Include AT LEAST 10-15 stories covering diverse topics. Focus on stories most important to Appalachian communities. Use a warm, community-focused tone. Start directly with <h2> tags.
"""

    try:
        log.info("Sending to Claude AI...")
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        html_content = response.content[0].text.strip()
        log.info("AI digest generated.")
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
            <p>Curated from 21 trusted Appalachian news sources.</p>
            <p style="text-align: center; margin: 20px 0;">
                <a class="subscribe-btn" href="https://jbranx.github.io/Appalachian-News-Aggregator">Subscribe for Daily Updates</a>
            </p>
            <p>Appalachian Daily is a news aggregator created by Jim Branscome. You can provide him feedback at <a href="mailto:jbranscome@gmail.com">jbranscome@gmail.com</a>.</p>
            <p><a href="https://github.com/jbranx/Appalachian-News-Aggregator">Powered by open-source automation</a></p>
            <p style="font-size: 12px; color: #bdc3c7;">*|LIST:UNSUB|*</p>  <!-- Mailchimp unsubscribe merge tag -->
        </div>
    </div>
</body>
</html>'''
    return full_html

# === SEND EMAIL ===
def send_email(html_body: str):
    api_key = os.getenv("MAILCHIMP_API_KEY")
    if api_key:
        try:
            client = MailchimpMarketing.Client()
            client.set_config({
                "api_key": api_key,
                "server": api_key.split('-')[-1]  # e.g., 'us1'
            })

            list_id = os.getenv("MAILCHIMP_LIST_ID")
            if list_id:
                # Add/update recipient
                recipient = os.getenv("RECIPIENT_EMAIL")
                if recipient:
                    subscriber_hash = hashlib.md5(recipient.lower().encode()).hexdigest()
                    log.info(f"Adding subscriber: {recipient}")
                    client.lists.add_or_update_list_member(
                        list_id=list_id,
                        subscriber_hash=subscriber_hash,
                        body={"email_address": recipient, "status": "subscribed"}
                    )

                # Create campaign
                log.info("Creating Mailchimp campaign...")
                today = datetime.now().strftime("%B %d, %Y")
                campaign = client.campaigns.create({
                    "type": "regular",
                    "recipients": {"list_id": list_id},
                    "settings": {
                        "subject_line": f"🏔️ Appalachian Daily • {today}",
                        "from_name": "Appalachian Daily",
                        "reply_to": os.getenv("EMAIL_ADDRESS", "noreply@appalachiandaily.com")
                    }
                })

                # Set content
                client.campaigns.set_campaign_content(
                    campaign_id=campaign["id"],
                    body={"html": html_body}
                )

                # Send
                log.info("Sending Mailchimp campaign...")
                response = client.campaigns.send(campaign_id=campaign["id"])
                log.info(f"✅ Campaign sent! ID: {campaign['id']} (unsubscribe auto-added)")
                return True
        except Exception as e:
            log.error(f"Mailchimp failed: {e} — falling back to Gmail")

    # Fallback to Gmail
    log.info("Sending via Gmail SMTP...")
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("RECIPIENT_EMAIL")

    if not all([sender, password, recipient]):
        log.error("Missing Gmail credentials — cannot send")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏔️ Appalachian Daily • {datetime.now().strftime('%B %d, %Y')}"
    msg["From"] = sender
    msg["To"] = recipient

    part = MIMEText(html_body, "html", "utf-8")
    msg.attach(part)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        log.info("✅ Email sent via Gmail!")
        return True
    except Exception as e:
        log.error(f"Gmail send failed: {e}")
        return False

# === MAIN ===
def main():
    log.info("Starting Appalachian Daily News Aggregator")

    articles = fetch_articles()
    if len(articles) < 3:
        log.error("Too few articles to proceed.")
        sys.exit(1)

    try:
        digest_html = generate_digest(articles)
    except Exception as e:
        log.error("AI summarization failed.")
        sys.exit(1)

    story_count = digest_html.count("<h3>")
    email_html = build_email(digest_html, story_count)
    success = send_email(email_html)

    if success:
        log.info(f"Digest complete: {story_count} stories sent!")
    else:
        log.error("Send failed — check secrets and logs.")

if __name__ == "__main__":
    main()
Update [Appalachian News] for auto-send and unsubscribe
    
