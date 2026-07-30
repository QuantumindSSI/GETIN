from datetime import datetime, timezone
from typing import Dict, List

from src.cryptorank_client import CryptoRankClient


class CurrencyMonitor:
    """Poll CryptoRank for live data on chosen currency symbols."""

    def __init__(self, client: CryptoRankClient, symbols: List[str]):
        self.client = client
        self.symbols = set(s.upper() for s in symbols)

    def check(self) -> List[Dict[str, str]]:
        """Return current market snapshot for the configured symbols."""
        results: List[Dict[str, str]] = []
        page = 1
        remaining = set(self.symbols)
        while remaining and page <= 10:
            data = self.client.get_currencies_list(page=page)
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                sym = (item.get("symbol") or "").upper()
                if sym in remaining:
                    results.append(
                        {
                            "symbol": sym,
                            "name": item.get("name", ""),
                            "price_usd": item.get("price"),
                            "market_cap_usd": item.get("marketCap"),
                            "checked_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    remaining.discard(sym)
            if not data.get("meta", {}).get("hasNextPage"):
                break
            page += 1
        return results