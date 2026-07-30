import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import tweepy

TWITTER_TOKENS_DIR = "twitter_tokens"
TWITTER_ENV_PREFIX = "TWITTER_"

# Set these in .env from developer.twitter.com
TWITTER_CLIENT_ID = os.getenv(f"{TWITTER_ENV_PREFIX}CLIENT_ID", "")
TWITTER_CLIENT_SECRET = os.getenv(f"{TWITTER_ENV_PREFIX}CLIENT_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv(f"{TWITTER_ENV_PREFIX}ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv(f"{TWITTER_ENV_PREFIX}ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv(f"{TWITTER_ENV_PREFIX}BEARER_TOKEN", "")


class TwitterConnector:
    """
    Connect to Twitter API v2 to post tweets and threads.
    Supports API key auth (bot account) or per-user OAuth tokens.
    Stores user access tokens in twitter_tokens/ directory.
    """

    def __init__(self, user_id: int):
        self.user_id = str(user_id)
        self.client: Optional[tweepy.Client] = None
        self.api: Optional[tweepy.API] = None
        os.makedirs(TWITTER_TOKENS_DIR, exist_ok=True)
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the Twitter client using configured credentials."""
        if TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_SECRET:
            self.client = tweepy.Client(
                consumer_key=TWITTER_CLIENT_ID or TWITTER_BEARER_TOKEN,
                consumer_secret=TWITTER_CLIENT_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET,
                bearer_token=TWITTER_BEARER_TOKEN,
            )
        elif TWITTER_BEARER_TOKEN:
            self.client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        else:
            self.client = None

    def is_connected(self) -> bool:
        """Check if Twitter client is authenticated."""
        if self.client is None:
            return False
        try:
            me = self.client.get_me()
            return me.data is not None
        except Exception:
            return False

    def post_tweet(self, text: str) -> Optional[str]:
        """Post a single tweet. Returns the tweet ID."""
        if not self.client:
            return None
        try:
            resp = self.client.create_tweet(text=text)
            return str(resp.data["id"])
        except tweepy.TooManyRequests as e:
            raise RuntimeError("Twitter rate limited. Wait 15 minutes.") from e
        except tweepy.Forbidden as e:
            raise RuntimeError("Twitter auth failed. Check API keys in .env.") from e
        except Exception as e:
            return f"Error: {str(e)[:100]}"

    def post_thread(self, tweets: List[str]) -> List[Dict[str, Any]]:
        """Post a Twitter thread — each tweet replies to the previous one."""
        results = []
        reply_to_id = None
        for i, text in enumerate(tweets):
            try:
                if reply_to_id is None:
                    resp = self.client.create_tweet(text=text)
                else:
                    resp = self.client.create_tweet(text=text, in_reply_to_tweet_id=reply_to_id)
                tid = str(resp.data["id"])
                reply_to_id = tid
                results.append({"index": i + 1, "tweet_id": tid, "ok": True})
            except Exception as e:
                results.append({"index": i + 1, "error": str(e)[:100], "ok": False})
                break
        return results

    def get_tweet_url(self, tweet_id: str) -> str:
        """Return the URL for a posted tweet."""
        username = self._get_username()
        return f"https://twitter.com/{username}/status/{tweet_id}"

    def _get_username(self) -> str:
        try:
            me = self.client.get_me()
            return me.data.username
        except Exception:
            return "i"

    def get_engagement_stats(self, tweet_id: str) -> Dict[str, Any]:
        """Get likes, retweets, and impressions for a tweet."""
        if not self.client:
            return {}
        try:
            resp = self.client.get_tweet(
                tweet_id,
                tweet_fields=["public_metrics"],
            )
            metrics = resp.data.public_metrics
            return {
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "impressions": metrics.get("impression_count", 0),
            }
        except Exception:
            return {"likes": 0, "retweets": 0, "replies": 0, "impressions": 0}


def store_user_token(user_id: int, access_token: str) -> None:
    """Store a user's Twitter OAuth token."""
    filepath = os.path.join(TWITTER_TOKENS_DIR, f"{user_id}.json")
    with open(filepath, "w") as f:
        json.dump({"user_id": user_id, "access_token": access_token, "stored_at": datetime.now(timezone.utc).isoformat()}, f)