import re
import requests

def extract_username_from_url(url):
    """
    Extract Instagram username from any Instagram URL.
    Handles:
      - Profile: https://www.instagram.com/username/
      - Post:    https://www.instagram.com/p/CODE/
      - Reel:    https://www.instagram.com/reel/CODE/
    Returns username string or None if not found.
    """
    url = url.strip()

    # Normalize URL
    if not url.startswith("http"):
        url = "https://" + url

    # Direct profile URL: instagram.com/username/
    profile_match = re.match(
        r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?:\?.*)?$", url
    )
    if profile_match:
        username = profile_match.group(1)
        # Exclude reserved paths
        if username not in ("p", "reel", "reels", "stories", "explore", "tv", "accounts"):
            return username

    # Post or Reel URL: instagram.com/p/CODE/ or instagram.com/reel/CODE/
    post_match = re.match(
        r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?", url
    )
    if post_match:
        return _extract_username_from_post(url)

    return None


def _extract_username_from_post(url):
    """Fetch an Instagram post page and extract the username from meta tags."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        text = resp.text

        # Try og:description: "username on Instagram: ..."
        og_desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', text)
        if og_desc:
            desc = og_desc.group(1)
            # Pattern: "username on Instagram"
            m = re.match(r'^([A-Za-z0-9_.]+)\s+on\s+Instagram', desc)
            if m:
                return m.group(1)

        # Try og:title: "username on Instagram: ..."
        og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', text)
        if og_title:
            title = og_title.group(1)
            m = re.match(r'^([A-Za-z0-9_.]+)\s+on\s+Instagram', title)
            if m:
                return m.group(1)

        # Try JSON-LD / __typename pattern
        username_match = re.search(r'"username"\s*:\s*"([A-Za-z0-9_.]+)"', text)
        if username_match:
            return username_match.group(1)

        return None

    except Exception as e:
        print(f"  [extractor] Error: {e}")
        return None
