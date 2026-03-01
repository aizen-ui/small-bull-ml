"""
Sentiment Analysis Module
Simple web scraping from Google News RSS for company news
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from urllib.parse import quote_plus

# Try to import VADER
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False


@dataclass
class NewsArticle:
    """Container for news article data"""
    title: str
    source: str
    date: str
    url: str
    snippet: str
    sentiment_score: float
    sentiment_label: str


@dataclass
class SentimentResult:
    """Container for overall sentiment analysis"""
    overall_score: float
    overall_label: str
    positive_count: int
    negative_count: int
    neutral_count: int
    articles: List[NewsArticle]
    key_themes: Dict[str, int]
    future_outlook: List[str]
    sources_summary: Dict[str, int]
    sentiment_trend: List[Dict] = field(default_factory=list)
    confidence_score: float = 0.0
    analysis_method: str = "vader"
    news_volume_score: float = 0.0
    top_positive_articles: List[NewsArticle] = field(default_factory=list)
    top_negative_articles: List[NewsArticle] = field(default_factory=list)
    llm_summary: str = ""


class GoogleNewsScraper:
    """Scrapes Google News RSS for company news"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search(self, company_name: str, days_back: int = 2) -> List[Dict]:
        """Search Google News RSS for company articles"""

        # Clean company name
        clean_name = company_name.lower()
        for suffix in [' ltd.', ' ltd', ' limited', ' inc.', ' inc', ' corp.', ' corp', ' pvt.', ' pvt', ' india']:
            clean_name = clean_name.replace(suffix, '')
        clean_name = clean_name.strip()

        print(f"Searching Google News for: {clean_name}")

        # Google News RSS URL
        query = quote_plus(f"{clean_name} stock")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

        articles = []

        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                print(f"Google News returned {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            print(f"Found {len(items)} items in RSS feed")

            cutoff_date = datetime.now() - timedelta(days=days_back)

            for item in items:
                try:
                    title = item.find('title').text if item.find('title') else ""
                    link = item.find('link').text if item.find('link') else ""
                    pub_date = item.find('pubDate').text if item.find('pubDate') else ""
                    source = item.find('source').text if item.find('source') else "Unknown"

                    # Check if company name appears in title
                    if clean_name.lower() not in title.lower():
                        continue

                    # Parse date
                    try:
                        article_date = datetime.strptime(pub_date[:25], '%a, %d %b %Y %H:%M:%S')
                        if article_date < cutoff_date:
                            continue
                        date_str = article_date.strftime('%Y-%m-%d')
                    except:
                        date_str = datetime.now().strftime('%Y-%m-%d')

                    articles.append({
                        'title': title,
                        'url': link,
                        'source': source,
                        'date': date_str,
                        'snippet': title  # Use title as snippet
                    })

                except Exception as e:
                    continue

            print(f"Found {len(articles)} relevant articles mentioning '{clean_name}'")

        except Exception as e:
            print(f"Error fetching Google News: {e}")

        return articles


class SentimentAnalyzer:
    """Main sentiment analyzer using Google News scraping"""

    def __init__(self, company_name: str, ticker: str = "", industry: str = "",
                 gemini_api_key: str = None, claude_api_key: str = None, news_api_key: str = None):
        self.company_name = company_name
        self.ticker = ticker
        self.industry = industry

        self.scraper = GoogleNewsScraper()

        # Initialize VADER
        self.vader = None
        if VADER_AVAILABLE:
            self.vader = SentimentIntensityAnalyzer()

    def analyze(self, days_back: int = 2) -> SentimentResult:
        """Run sentiment analysis"""
        print(f"\n{'='*60}")
        print(f"Analyzing sentiment for: {self.company_name}")
        print(f"{'='*60}\n")

        # Scrape news
        raw_articles = self.scraper.search(self.company_name, days_back)

        # Analyze sentiment
        articles = []
        positive = 0
        negative = 0
        neutral = 0
        total_score = 0
        sources = defaultdict(int)

        for raw in raw_articles:
            title = raw['title']
            score = 0
            label = "neutral"

            if self.vader:
                scores = self.vader.polarity_scores(title)
                score = scores['compound']
                if score >= 0.05:
                    label = "positive"
                    positive += 1
                elif score <= -0.05:
                    label = "negative"
                    negative += 1
                else:
                    neutral += 1

            total_score += score
            sources[raw['source']] += 1

            articles.append(NewsArticle(
                title=title,
                source=raw['source'],
                date=raw['date'],
                url=raw['url'],
                snippet=raw['snippet'],
                sentiment_score=round(score, 3),
                sentiment_label=label
            ))

        # Calculate overall
        if articles:
            avg_score = total_score / len(articles)
            if avg_score >= 0.1:
                overall_label = "Positive"
            elif avg_score <= -0.1:
                overall_label = "Negative"
            else:
                overall_label = "Neutral"
            confidence = min(0.9, len(articles) * 0.1)
        else:
            avg_score = 0
            overall_label = "Neutral"
            confidence = 0

        # Extract themes
        themes = self._extract_themes(articles)

        # Build summary
        if articles:
            summary = f"Found {len(articles)} news articles about {self.company_name}. "
            summary += f"Sentiment: {positive} positive, {neutral} neutral, {negative} negative."
        else:
            summary = f"No recent news found for {self.company_name}."

        return SentimentResult(
            overall_score=round(avg_score, 3),
            overall_label=overall_label,
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
            articles=articles,
            key_themes=themes,
            future_outlook=[],
            sources_summary=dict(sources),
            confidence_score=round(confidence, 2),
            analysis_method="Google News + VADER",
            news_volume_score=min(100, len(articles) * 10),
            top_positive_articles=[a for a in articles if a.sentiment_label == 'positive'][:5],
            top_negative_articles=[a for a in articles if a.sentiment_label == 'negative'][:5],
            llm_summary=summary
        )

    def _extract_themes(self, articles: List[NewsArticle]) -> Dict[str, int]:
        """Extract themes from articles"""
        theme_keywords = {
            "Earnings": ["earnings", "profit", "revenue", "quarterly", "results"],
            "Stock Price": ["stock", "shares", "price", "rally", "surge", "fall"],
            "Growth": ["expansion", "growth", "acquisition", "deal"],
            "Management": ["ceo", "director", "appointed", "board"],
            "Dividend": ["dividend", "payout", "buyback"],
        }

        all_text = " ".join([a.title.lower() for a in articles])
        themes = {}

        for theme, keywords in theme_keywords.items():
            count = sum(all_text.count(kw) for kw in keywords)
            if count > 0:
                themes[theme] = count

        return dict(sorted(themes.items(), key=lambda x: x[1], reverse=True)[:5])


def generate_sentiment_summary(result: SentimentResult, company_name: str) -> str:
    """Generate sentiment summary"""
    if result.llm_summary:
        return result.llm_summary

    total = result.positive_count + result.negative_count + result.neutral_count

    if total == 0:
        return f"No recent news articles found for {company_name}."

    summary = f"**{result.overall_label}** sentiment (score: {result.overall_score:.2f})\n\n"
    summary += f"Analyzed {total} articles: {result.positive_count} positive, "
    summary += f"{result.neutral_count} neutral, {result.negative_count} negative.\n\n"
    summary += f"**Method:** {result.analysis_method}"

    if result.key_themes:
        themes = list(result.key_themes.keys())[:3]
        summary += f"\n\n**Themes:** {', '.join(themes)}"

    return summary
