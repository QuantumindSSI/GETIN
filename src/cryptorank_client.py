import os
import requests
from typing import Any, Dict, List, Optional


class CryptoRankClient:
    """Fetch read-only data from CryptoRank API v3."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CRYPTORANK_API_KEY")
        if not self.api_key:
            raise ValueError("CRYPTORANK_API_KEY is missing.")
        self.base_url = "https://api.cryptorank.io/v3"
        self.session = requests.Session()
        self.session.headers.update({"X-Api-Key": self.api_key})

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a GET request and return JSON."""
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_currencies(
        self, limit: int = 50, offset: int = 0, symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch currency list. Optionally filter by symbols."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._get("/currencies", params)

    def get_funds(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Fetch funding rounds data."""
        return self._get("/funds", {"limit": limit, "offset": offset})

    def get_token_unlocks(self, limit: int = 100) -> Dict[str, Any]:
        """Fetch token unlock schedules."""
        return self._get("/token-unlocks", {"limit": limit})

    def get_drop_hunting(self, limit: int = 100) -> Dict[str, Any]:
        """Fetch CryptoRank Drop Hunting list."""
        return self._get("/drop-hunting", {"limit": limit})
