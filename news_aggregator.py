""" Appalachian News Aggregator Fetches news from quality Appalachian regional sources via RSS feeds """

import os
import feedparser
from datetime import datetime, timedelta
from anthropic import Anthropic
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

# Comprehensive Appalachian news sources
RSS_FEEDS = {
    # Core Investigative & Policy
    'Kentucky Lantern': 'https://kentuckylantern.com/feed/',
    'Cardinal News': 'https://cardinalnews.org/feed/',
    'West Virginia Watch': 'https://www.wvwatch.org/feed/',
    'Mountain State Spotlight': 'https://mountainstatespotlight.org/feed/',
    'Ohio Valley ReSource': 'https://ohiovalleyresource.org/feed/',
    # Regional Focus & Culture
    'Daily Yonder': 'https://dailyyonder.com/feed/',
    '100 Days in Appalachia': 'https://www.100daysinappalachia.com/feed/',
    'Appalachian Voices': 'https://appvoices.org/feed/',
    'Scalawag Magazine': 'https://scalawagmagazine.org/feed/',
    # Major Regional Papers
    'Charleston Gazette-Mail': 'https://www.wvgazettemail.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&c[]=news*&f=rss',
    'Bristol Herald Courier': 'https://www.heraldcourier.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss',
    'Lexington Herald-Leader': 'https://www.kentucky.com/news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true',
    # Local & Community News
    'WYMT Mountain News': 'https://www.wymt.com/news/?format=rss',
    'State Journal WV': 'https://www.wvnews.com/statejournal/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss',
    'West Virginia Public Broadcasting': 'https://www.wvpublic.org/rss.xml',
    # Environmental & Energy
    'Inside Climate News - Appalachia': 'https://insideclimatenews.org/category/appalachia/feed/',
    'Southern Environmental Law Center': 'https://www.southernenvironment.org/feed/',
    # Additional Regional Sources
    'Highlander Research': 'https://www.highlandercenter.org/feed/',
    'West Virginia MetroNews': 'https://wvmetronews.com/feed/',
    'Bluefield Daily Telegraph': 'https://www.bdtonline.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss',
}

def fetch_rss_feeds():
    """Fetch articles from all RSS feeds with robust error handling"""
    log.info(f"Fetching from {len(RSS_FEEDS)} Appalachian news sources...")
    log.info(f"Looking for articles from the last 72 hours")

    all_articles = []
    cutoff_time = datetime.now() - timedelta(hours=72)  # 3 days
    successful_sources = 0
    failed_sources = []

    for source_name, feed_url in RSS_FEEDS.items():
        try:
            log.info(f" → {source_name}...")
            # Parse feed
            feed = feedparser.parse(feed_url)

            # Check if feed parsed successfully
            if hasattr(feed, 'bozo') and feed.bozo:
                log.warning(f"Parse warning for {source_name}")
            if not feed.entries:
                log.warning(f"No entries found for {source_name}")
                failed_sources.append(source_name)
                continue

            articles_found = 0
            # Get up to 20 recent articles per source
            for entry in feed.entries[:20]:
                try:
                    # Get publish date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            pub_date = datetime(*entry.published_parsed[:6])
                        except:
                            pass
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        try:
                            pub_date = datetime(*entry.updated_parsed[:6])
                        except:
                            pass

                    # If no date found, skip this article
                    if not pub_date:
                        continue

                    # Only include recent articles
                    if pub_date > cutoff_time:
                        # Get summary/description
                        summary = ''
                        if hasattr(entry, 'summary'):
                            summary = entry.summary
                        elif hasattr(entry, 'description'):
                            summary = entry.description
                        elif hasattr(entry, 'content'):
                            summary = entry.content[0].value if entry.content else ''

                        # Skip sports
                        lower_title = entry.get('title', '').lower()
                        lower_summary = summary.lower()
                        sports_keywords = ['game', 'score', 'sports', 'athletics', 'team', 'player', 'coach', 'ncaa', 'football']
                        if any(kw in lower_title or kw in lower_summary for kw in sports_keywords):
                            continue

                        article = {
                            'title': entry.get('title', 'No title'),
                            'summary': summary[:500],  # Limit summary length
                            'link': entry.get('link', ''),
                            'source': source_name,
                            'published': pub_date
                        }
                        all_articles.append(article)
                        articles_found += 1
                except Exception as e:
                    continue

            if articles_found > 0:
                log.info(f"{source_name}: {articles_found} articles")
                successful_sources += 1
            else:
                log.warning(f"{source_name}: No recent articles")
                failed_sources.append(source_name)

        except Exception as e:
            log.error(f"{source_name}: Error - {str(e)[:50]}")
            failed_sources.append(source_name)
            continue

    # Sort by date, most recent first
    all_articles.sort(key=lambda x: x['published'], reverse=True)

    log.info(f"Total articles collected: {len(all_articles)}")
    if failed_sources:
        log.warning(f"Failed sources: {', '.join(failed_sources)}")

    return all_articles


def create_summary_with_claude(articles):
    """Use Claude to create an intelligent summary"""
    log.info("Creating AI-powered digest...")

    if not articles:
        return "No recent Appalachian news articles found."

    # Use top 40 most recent articles
    articles_text = "\n\n".join([
        f"[{article['source']}] {article['title']}\n{article['summary'][:400]}...\nLink: {article['link']}"
        for article in articles[:40]
    ])

    prompt = f"""
You are creating a daily news digest for Appalachian communities. Here are recent articles from trusted regional sources:

{articles_text}

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
3. Include source and link: <p><strong>Source:</strong> <a href="link">Read more at [Source Name]</a></p>

Include AT LEAST 10-15 stories covering diverse topics. Focus on stories most important to Appalachian communities. Use a warm, community-focused tone. Start directly with <h2> tags.
"""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,  # Increased for more stories
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        log.info("Digest created successfully")
        return message.content[0].text
    except Exception as e:
        log.error(f"Error creating summary: {e}")
        return f"Error generating digest: {str(e)}"


def create_html_email(summary_content, article_count):
    """Create beautiful HTML email"""
    today = datetime.now().strftime("%B %d, %Y")
    header_style = """
        background: linear-gradient(135deg, #1e4620, #2d5016, #4a7c59);
        color: white;
        padding: 30px;
        text-align: center;
        font-family: Georgia, serif;
        border-radius: 8px 8px 0 0;
    """
    body_style = """
        background: white;
        padding: 40px 35px;
        font-family: Georgia, serif;
        line-height: 1.7;
        color: #2c3e50;
        font-size: 16px;
    """
    h2_style = """
        color: #2d5016;
        font-size: 24px;
        font-weight: 600;
        border-left: 5px solid #4a7c59;
        padding-left: 15px;
        margin-top: 35px;
    """
    h3_style = """
        color: #1e4620;
        font-size: 19px;
        margin: 25px 0 10px 0;
    """
    a_style = """
        color: #2d5016;
        text-decoration: none;
    """
    a_hover = "text-decoration: underline;"

    footer_style = """
        background: #34495e;
        color: #ecf0f1;
        padding: 30px;
        text-align: center;
        font-size: 14px;
        border-radius: 0 0 8px 8px;
    """

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Appalachian Daily - {today}</title>
    <style>
        body {{ margin: 0; background: #f4f4f4; padding: 20px 0; }}
        .container {{ max-width: 650px; margin: 0 auto; background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
        .header {{{header_style}}}
        .body {{{body_style}}}
        h2 {{{h2_style}}}
        h3 {{{h3_style}}}
        a {{{a_style}}}
        a:hover {{{a_hover}}}
        .footer {{{footer_style}}}
        .mountain {{ font-size: 42px; }}
        @media (max-width: 600px) {{ .body {{ padding: 20px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="mountain">🏔️</div>
            <h1 style="margin:10px 0; font-size:36px; font-weight:300;">Appalachian Daily</h1>
            <p style="margin:5px 0; font-size:18px;">{today} • {article_count} stories</p>
        </div>
        <div class="body">
            {summary_content}
        </div>
        <div class="footer">
            <p>Curated from 21 trusted Appalachian news sources.</p>
            <p><a href="https://github.com/jbranx/Appalachian-News-Aggregator" style="color:#ecf0f1;">Powered by open-source automation</a></p>
        </div>
    </div>
</body>
</html>
"""


def send_email(subject, html_body):
    """Send email via Mailchimp (with Gmail fallback)"""
    log.info("📧 Sending email via Mailchimp...")
    
    # Try Mailchimp first
    api_key = os.getenv("MAILCHIMP_API_KEY")
    if api_key:
        try:
            import mailchimp_marketing as MailchimpMarketing
            from mailchimp_marketing.api_client import ApiClientError
            import hashlib
            
            client = MailchimpMarketing.Client()
            client.set_config({
                "api_key": api_key,
                "server": api_key.split('-')[-1]  # e.g., 'us1'
            })
            
            list_id = os.getenv("MAILCHIMP_LIST_ID")
            if not list_id:
                log.warning("⚠️ No MAILCHIMP_LIST_ID secret — skipping Mailchimp")
            else:
                # Add/update recipient (for testing)
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
                campaign_subject = f"🏔️ Appalachian Daily • {today}"
                campaign = client.campaigns.create({
                    "type": "regular",
                    "recipients": {"list_id": list_id},
                    "settings": {
                        "subject_line": campaign_subject,
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
                log.info(f"✅ Campaign sent! ID: {campaign['id']}")
                return True  # Success
        
        except ApiClientError as error:
            log.warning(f"⚠️ Mailchimp API error: {error.text} — falling back to Gmail")
        except Exception as e:
            log.warning(f"⚠️ Mailchimp send failed: {e} — falling back to Gmail")
    
    # Fallback to Gmail
    log.info("📧 Falling back to Gmail SMTP...")
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.getenv("EMAIL_ADDRESS")
        msg['To'] = os.getenv("RECIPIENT_EMAIL")
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
        log.info("✅ Email sent via Gmail!")
        return True
    except Exception as e:
        log.error(f"❌ Gmail send failed: {e}")
        return False


def main():
    """Main execution"""
    log.info("\n" + "="*60)
    log.info("APPALACHIAN NEWS AGGREGATOR STARTING")
    log.info("="*60)

    articles = fetch_rss_feeds()
    if not articles:
        log.warning("No articles found. Exiting.")
        return

    if len(articles) < 5:
        log.warning(f"WARNING: Only {len(articles)} articles found. This is unusually low.")

    summary = create_summary_with_claude(articles)
    html_email = create_html_email(summary, len(articles))
    today = datetime.now().strftime("%B %d, %Y")
    send_email(f"Appalachian Daily - {today}", html_email)

    log.info("="*60)
    log.info("DONE!")
    log.info("="*60 + "\n")


if __name__ == "__main__":
    main()
