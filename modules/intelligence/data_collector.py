"""
Data Collector — Multi-source world-data aggregator.

Collects news, trends, and web content from:
- RSS feeds (Google News, TechCrunch, Reuters) — no API key required
- NewsAPI (optional, 100 req/day free tier)
- Google Trends (via pytrends)
- Generic web scraping fallback
"""

import os
import re
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger("SAI.Intelligence.DataCollector")


# ── Default RSS feeds ──
DEFAULT_RSS_FEEDS = {
    "google_news": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
    "techcrunch": "https://techcrunch.com/feed/",
    "reuters_tech": "https://www.rss-bridge.org/bridge01/?action=display&bridge=Reuters&feed=technology&format=Atom",
    "ars_technica": "https://feeds.arstechnica.com/arstechnica/index",
}


class DataCollector:
    """Collects world data from multiple sources."""

    def __init__(self, newsapi_key: Optional[str] = None, cache_ttl: int = 300):
        self.newsapi_key = newsapi_key or os.getenv("NEWSAPI_KEY", "")
        self.cache_ttl = cache_ttl  # seconds
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}

    def collect(self, query: str, sources: Optional[List[str]] = None, max_items: int = 30) -> List[Dict[str, Any]]:
        """Collects data from specified sources. Returns list of DataPoint dicts.
        
        Args:
            query: Search query (e.g. "AI trends", "crypto market")
            sources: List of source types: "news", "rss", "trends", "scrape"
            max_items: Maximum items to return
        """
        if sources is None:
            sources = ["rss", "news", "trends"]

        cache_key = hashlib.md5(f"{query}:{','.join(sources)}".encode()).hexdigest()
        if cache_key in self._cache and (time.time() - self._cache_ts.get(cache_key, 0)) < self.cache_ttl:
            logger.info("Returning cached data for query: %s", query)
            return self._cache[cache_key]

        all_data: List[Dict[str, Any]] = []

        for source in sources:
            try:
                if source == "rss":
                    all_data.extend(self._collect_rss(query, max_items=max_items))
                elif source == "news" and self.newsapi_key:
                    all_data.extend(self._collect_newsapi(query, max_items=max_items))
                elif source == "trends":
                    all_data.extend(self._collect_trends(query))
                elif source == "scrape":
                    all_data.extend(self._collect_scrape(query, max_items=5))
            except Exception as e:
                logger.warning("Data collection from %s failed: %s", source, e)

        # Deduplicate by title
        seen_titles = set()
        unique_data = []
        for item in all_data:
            title_hash = hashlib.md5(item.get("title", "").lower().encode()).hexdigest()
            if title_hash not in seen_titles:
                seen_titles.add(title_hash)
                unique_data.append(item)

        result = unique_data[:max_items]
        self._cache[cache_key] = result
        self._cache_ts[cache_key] = time.time()

        logger.info("Collected %d data points for query: %s", len(result), query)
        return result

    # ── RSS Feeds ──
    def _collect_rss(self, query: str, max_items: int = 20) -> List[Dict[str, Any]]:
        """Collects from RSS feeds. No API key required."""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed — skipping RSS collection")
            return []

        results = []
        for feed_name, feed_url in DEFAULT_RSS_FEEDS.items():
            try:
                url = feed_url.format(query=query.replace(" ", "+"))
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_items // len(DEFAULT_RSS_FEEDS) + 1]:
                    # Strip HTML from summary
                    summary = re.sub(r'<[^>]+>', '', entry.get("summary", ""))
                    results.append({
                        "source": f"rss/{feed_name}",
                        "title": entry.get("title", "No title"),
                        "text": summary[:500],
                        "url": entry.get("link", ""),
                        "timestamp": entry.get("published", datetime.now().isoformat()),
                        "type": "article",
                    })
            except Exception as e:
                logger.debug("RSS feed %s failed: %s", feed_name, e)

        return results

    # ── NewsAPI ──
    def _collect_newsapi(self, query: str, max_items: int = 15) -> List[Dict[str, Any]]:
        """Collects from NewsAPI (requires key in .env)."""
        import requests

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "sortBy": "publishedAt",
            "pageSize": min(max_items, 100),
            "apiKey": self.newsapi_key,
            "language": "en",
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("NewsAPI request failed: %s", e)
            return []

        results = []
        for article in data.get("articles", []):
            results.append({
                "source": f"newsapi/{article.get('source', {}).get('name', 'unknown')}",
                "title": article.get("title", ""),
                "text": article.get("description", "") or article.get("content", ""),
                "url": article.get("url", ""),
                "timestamp": article.get("publishedAt", ""),
                "type": "news",
            })

        return results

    # ── Google Trends ──
    def _collect_trends(self, query: str) -> List[Dict[str, Any]]:
        """Collects interest-over-time data from Google Trends."""
        try:
            from pytrends.request import TrendReq
        except ImportError:
            logger.warning("pytrends not installed — skipping trends collection")
            return []

        try:
            pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
            keywords = [kw.strip() for kw in query.split(",")][:5]
            pytrends.build_payload(keywords, timeframe='now 7-d')
            interest = pytrends.interest_over_time()

            if interest.empty:
                return []

            results = []
            for keyword in keywords:
                if keyword in interest.columns:
                    values = interest[keyword].tolist()
                    results.append({
                        "source": "google_trends",
                        "title": f"Trend: {keyword}",
                        "text": f"7-day interest for '{keyword}': peak={max(values)}, latest={values[-1]}, avg={sum(values)//len(values)}",
                        "url": f"https://trends.google.com/trends/explore?q={keyword.replace(' ', '+')}",
                        "timestamp": datetime.now().isoformat(),
                        "type": "trend",
                        "trend_data": values,
                    })

            # Related queries
            try:
                related = pytrends.related_queries()
                for keyword in keywords:
                    if keyword in related and related[keyword].get("rising") is not None:
                        rising = related[keyword]["rising"]
                        if not rising.empty:
                            top_rising = rising.head(5)["query"].tolist()
                            results.append({
                                "source": "google_trends/related",
                                "title": f"Rising queries for: {keyword}",
                                "text": f"Trending related searches: {', '.join(top_rising)}",
                                "url": "",
                                "timestamp": datetime.now().isoformat(),
                                "type": "trend_related",
                            })
            except Exception:
                pass

            return results

        except Exception as e:
            logger.warning("Google Trends collection failed: %s", e)
            return []

    # ── Web Scraping Fallback ──
    def _collect_scrape(self, query: str, max_items: int = 5) -> List[Dict[str, Any]]:
        """Scrapes search results via DuckDuckGo HTML."""
        import requests

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("beautifulsoup4 not installed — skipping scrape collection")
            return []

        try:
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0)"}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")

            results = []
            for item in soup.select(".result__body")[:max_items]:
                title_el = item.select_one(".result__a")
                snippet_el = item.select_one(".result__snippet")
                if title_el:
                    results.append({
                        "source": "scrape/duckduckgo",
                        "title": title_el.get_text(strip=True),
                        "text": snippet_el.get_text(strip=True) if snippet_el else "",
                        "url": title_el.get("href", ""),
                        "timestamp": datetime.now().isoformat(),
                        "type": "web",
                    })

            return results

        except Exception as e:
            logger.warning("Web scraping failed: %s", e)
            return []
