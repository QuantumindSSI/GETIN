from datetime import datetime, timezone
from typing import Dict, List

from src.cryptorank_client import CryptoRankClient


class CurrencyMonitor:
    """Poll CryptoRank for live data on chosen currency symbols."""

    def __init__(self, client: CryptoRankClient, symbols: List[str]):
        self.client = client
        self.symbols = [s.upper() for s in symbols]

    def check(self) -> List[Dict[str, str]]:
        """Return current market snapshot for the configured symbols."""
        data = self.client.get_currencies(symbols=self.symbols)
        results: List[Dict[str, str]] = []
        for item in data.get("data", []):
            sym = item.get("symbol", "").upper()
            if sym not in self.symbols:
                continue
            results.append(
                {
                    "symbol": sym,
                    "name": item.get("name", ""),
                    "price_usd": item.get("price", {}).get("usd"),
                    "market_cap_usd": item.get("marketCap", {}).get("usd"),
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        return results
