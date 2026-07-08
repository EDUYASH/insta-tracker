import requests
from bs4 import BeautifulSoup
import re

def scrape_socialblade(username):
    """Scrape follower stats for an Instagram username from Social Blade."""
    url = f"https://socialblade.com/instagram/user/{username}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"  [!] Failed to fetch Social Blade for @{username} (HTTP {response.status_code})")
            return None

        page_text = response.text

        # Extract followers count
        followers = None
        followers_match = re.search(r'"followers"\s*:\s*"?([\d,]+)"?', page_text, re.IGNORECASE)
        if followers_match:
            followers = int(followers_match.group(1).replace(",", ""))

        # Extract following count
        following = None
        following_match = re.search(r'"following"\s*:\s*"?([\d,]+)"?', page_text, re.IGNORECASE)
        if following_match:
            following = int(following_match.group(1).replace(",", ""))

        # Extract media/posts count
        posts = None
        posts_match = re.search(r'"media"\s*:\s*"?([\d,]+)"?', page_text, re.IGNORECASE)
        if posts_match:
            posts = int(posts_match.group(1).replace(",", ""))

        # Fallback: get from large numbers
        if not followers:
            soup = BeautifulSoup(page_text, "html.parser")
            stat_spans = soup.find_all("span", style=re.compile("font-size", re.IGNORECASE))
            for span in stat_spans:
                text = span.get_text(strip=True).replace(",", "")
                if text.isdigit() and int(text) > 100:
                    if not followers:
                        followers = int(text)

        return {
            "username": username,
            "followers": followers,
            "following": following,
            "posts": posts,
            "url": url,
        }

    except requests.exceptions.Timeout:
        print(f"  [!] Timeout fetching @{username}")
        return None
    except Exception as e:
        print(f"  [!] Error scraping @{username}: {e}")
        return None
