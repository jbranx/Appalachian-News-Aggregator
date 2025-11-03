"""
Appalachian News Aggregator
Fetches news from quality Appalachian regional sources via RSS feeds
"""

import os
import feedparser
from datetime import datetime, timedelta
from anthropic import Anthropic

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Quality Appalachian news sources
RSS_FEEDS = {
    # Investigative & Policy
    'Kentucky Lantern': 'https://kentuckylantern.com/feed/',
    'Cardinal News': 'https://cardinalnews.org/feed/',
    'West Virginia Watch': 'https://www.wvwatch.org/feed/',
    'Ohio Valley ReSource': 'https://ohiovalleyresource.org/feed/',
    
    # Regional Focus
    'Daily Yonder': 'https://dailyyonder.com/feed/',
    '100 Days in Appalachia': 'https://www.100daysinappalachia.com/feed/',
    'Appalachian Voices': 'https://appvoices.org/feed/',
    
    # Major Regional Papers
    'Charleston Gazette-Mail': 'https://www.wvgazettemail.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&c[]=news*&f=rss',
    'Bristol Herald Courier': 'https://www.heraldcourier.com/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss',
    
    # Local News
    'WYMT Mountain News': 'https://www.wymt.com/news/?format=rss',
    'State Journal WV': 'https://www.wvnews.com/statejournal/search/?q=&t=article&l=25&d=&d1=&d2=&s=start_time&sd=desc&f=rss',
}

def fetch_rss_feeds():
    """Fetch articles from all RSS feeds"""
    print(f"📡 Fetching from {len(RSS_FEEDS)} Appalachian news sources...")
    
    all_articles = []
    cutoff_time = datetime.now() - timedelta(hours=48)
    
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            print(f"  → Checking {source_name}...")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:10]:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6])
                
                if pub_date and pub_date > cutoff_time:
                    article = {
                        'title': entry.get('title', 'No title'),
                        'summary': entry.get('summary', entry.get('description', 'No description')),
                        'link': entry.get('link', ''),
                        'source': source_name,
                        'published': pub_date
                    }
                    all_articles.append(article)
            
            print(f"    ✓ Found {len([a for a in all_articles if a['source'] == source_name])} recent articles")
                    
        except Exception as e:
            print(f"    ✗ Error fetching {source_name}: {e}")
            continue
    
    all_articles.sort(key=lambda x: x['published'], reverse=True)
    
    print(f"\n✅ Total articles collected: {len(all_articles)}")
    return all_articles

def create_summary_with_claude(articles):
    """Use Claude to create an intelligent summary"""
    print("🤖 Creating AI-powered digest...")
    
    if not articles:
        return "<p>No recent Appalachian news articles found.</p>"
    
    articles_text = "\n\n".join([
        f"[{article['source']}] {article['title']}\n{article['summary'][:300]}...\nLink: {article['link']}"
        for article in articles[:30]
    ])
    
    prompt = f"""You are creating a daily news digest for Appalachian communities. Here are recent articles from trusted regional sources:

{articles_text}

Create a well-organized daily digest email using ONLY these HTML elements:
- <h2>Section Title</h2> for main categories
- <h3>Story Headline</h3> for individual stories
- <p>Content here</p> for all text paragraphs
- <a href="url">Link text</a> for article links
- <strong>text</strong> for emphasis

DO NOT use Markdown (no #, **, or ---). Only use HTML tags.

Organize stories into these categories as relevant:
- Economy & Jobs
- Energy & Environment  
- Health & Social Issues
- Education
- Politics & Policy
- Community & Culture

For each story:
1. Write a clear <h3> headline
2. Summarize in 2-3 sentences in a <p> tag
3. Include source and link: <p><strong>Source:</strong> <a href="link">Read more at [Source Name]</a></p>

Focus on stories most important to Appalachian communities. Use a warm, community-focused tone. Start directly with <h2> tags."""

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        print("✅ Digest created successfully")
        return message.content[0].text
    except Exception as e:
        print(f"❌ Error creating summary: {e}")
        return f"<p>Error generating digest: {str(e)}</p>"

def create_html_email(summary_content, article_count):
    """Create beautiful HTML email"""
    today = datetime.now().strftime("%B %d, %Y")
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ 
            font-family: 'Georgia', serif; 
            line-height: 1.7; 
            color: #2c3e50; 
            background: #f4f4f4; 
            margin: 0;
            padding: 0;
        }}
        .container {{ 
            max-width: 650px; 
            margin: 20px auto; 
            background: white; 
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        .header {{ 
            background: linear-gradient(135deg, #1e4620, #2d5016, #4a7c59);
            color: white; 
            padding: 40px 30px; 
            text-align: center;
            border-bottom: 4px solid #8b7355;
        }}
        .header h1 {{ 
            margin: 0; 
            font-size: 36px; 
            font-weight: 300;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header .emoji {{ font-size: 42px; margin-bottom: 10px; }}
        .header p {{ 
            margin: 15px 0 5px 0; 
            font-size: 18px; 
            opacity: 0.95;
        }}
        .header .count {{
            font-size: 14px;
            opacity: 0.8;
            font-style: italic;
        }}
        .content {{ 
            padding: 40px 35px;
            background: #ffffff;
        }}
        .content h2 {{ 
            color: #2d5016; 
            border-left: 5px solid #4a7c59;
            padding-left: 15px;
            margin-top: 35px;
            margin-bottom: 20px;
            font-size: 24px;
            font-weight: 600;
        }}
        .content h2:first-child {{ margin-top: 0; }}
        .content h3 {{ 
            color: #1e4620; 
            margin-top: 25px; 
            margin-bottom: 10px;
            font-size: 19px;
            line-height: 1.4;
        }}
        .content p {{ 
            margin: 12px 0; 
            font-size: 16px;
            line-height: 1.7;
        }}
        .content a {{
            color: #2d5016;
            text-decoration: none;
            border-bottom: 1px solid #4a7c59;
        }}
        .content a:hover {{
            color: #4a7c59;
            border-bottom: 2px solid #2d5016;
        }}
        .footer {{ 
            background: #34495e; 
            color: #ecf0f1;
            padding: 30px; 
            text-align: center;
            font-size: 14px;
        }}
        .footer p {{ margin: 8px 0; }}
        .footer a {{
            color: #4a7c59;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="emoji">🏔️</div>
            <h1>Appalachian Daily</h1>
            <p>{today}</p>
            <p class="count">{article_count} stories from across the region</p>
        </div>
        <div class="content">
            {summary_content}
        </div>
        <div class="footer">
            <p><strong>Your daily digest of Appalachian regional news</strong></p>
            <p>Curated from trusted local sources | Powered by AI</p>
            <p style="margin-top: 15px; font-size: 12px; opacity: 0.8;">
                Sources include Kentucky Lantern, Cardinal News, West Virginia Watch,<br>
                Daily Yonder, 100 Days in Appalachia, and other regional outlets
            </p>
        </div>
    </div>
</body>
</html>"""

def send_email(subject, html_body):
    """Send email via Gmail SMTP"""
    print("📧 Sending email...")
    
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
        
        print("✅ Email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

def main():
    """Main execution"""
    print("\n" + "="*60)
    print("🏔️  APPALACHIAN NEWS AGGREGATOR STARTING")
    print("="*60 + "\n")
    
    articles = fetch_rss_feeds()
    
    if not articles:
        print("⚠️  No articles found. Exiting.")
        return
    
    summary = create_summary_with_claude(articles)
    html_email = create_html_email(summary, len(articles))
    
    today = datetime.now().strftime("%B %d, %Y")
    send_email(f"🏔️ Appalachian Daily - {today}", html_email)
    
    print("\n" + "="*60)
    print("✅ DONE!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
