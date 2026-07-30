import os
import requests
from typing import Any, Dict, List, Optional


class CryptoRankClient:
    """Fetch read-only data from CryptoRank API v3."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CRYPTORANK_API_KEY")
        if not self.api_key:
            raise ValueError("CRYPTORANK_API_KEY is missing.")
        self.base_url = "https://api.cryptorank.io"
        self.session = requests.Session()
        self.session.headers.update({"X-Api-Key": self.api_key})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a GET request and return JSON."""
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_currencies_list(self, page: int = 1, sort_by: str = "rank") -> Dict[str, Any]:
        """Fetch paginated currency market data from /v3/currencies/list."""
        return self._get("/v3/currencies/list", {"page": page, "sortBy": sort_by})

    def search_currency(self, query: str) -> Dict[str, Any]:
        """Resolve a name or ticker to an id via /v3/currencies/search."""
        return self._get("/v3/currencies/search", {"query": query})

    def get_currency_profile(self, currency_id: int) -> Dict[str, Any]:
        """Fetch full profile for one currency by its id."""
        return self._get(f"/v3/currencies/{currency_id}")

    def get_global_snapshot(self) -> Dict[str, Any]:
        """Fetch global market snapshot (total mcap, volume, dominance)."""
        return self._get("/v3/global/market")

    def get_funds(self, page: int = 1) -> Dict[str, Any]:
        """Fetch funding rounds data. Requires Advanced plan or higher."""
        return self._get("/v3/funds/list", {"page": page})

    def get_token_unlocks(self, page: int = 1) -> Dict[str, Any]:
        """Fetch upcoming token unlocks. Requires Pro plan or higher."""
        return self._get("/v3/vesting/unlocks/upcoming", {"page": page})

    def get_drop_hunting(self, page: int = 1) -> Dict[str, Any]:
        """Fetch CryptoRank Drop Hunting activities. Requires Advanced plan or higher."""
        return self._get("/v3/drophunting/activities", {"page": page})