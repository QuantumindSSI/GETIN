import base64
import hashlib
import hmac
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

KRAKEN_API_URL = "https://api.kraken.com"


class KrakenClient:
    """
    Minimal but functional Kraken REST client for GBP → crypto on-ramp.
    Supports balance checks, market orders, and withdrawals.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or os.getenv("KRAKEN_API_KEY")
        self.api_secret = api_secret or os.getenv("KRAKEN_API_SECRET")
        if not self.api_key or not self.api_secret:
            raise ValueError("KRAKEN_API_KEY and KRAKEN_API_SECRET required in .env")
        self.http = httpx.Client(timeout=30.0)

    def _sign(self, urlpath: str, data: Dict[str, Any]) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    def _request(self, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{KRAKEN_API_URL}{path}"
        headers = {}
        if data is None:
            resp = self.http.get(url)
        else:
            data["nonce"] = int(time.time() * 1000)
            headers = {
                "API-Key": self.api_key,
                "API-Sign": self._sign(path, data),
            }
            resp = self.http.post(url, data=data, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        if result.get("error"):
            raise RuntimeError(f"Kraken API error: {result['error']}")
        return result.get("result", {})

    def get_ticker(self, pair: str) -> Dict[str, Any]:
        """Get current price for a pair (e.g., XETHZGBP)."""
        return self._request("/0/public/Ticker", {"pair": pair})

    def get_balance(self) -> Dict[str, float]:
        """Return account balances."""
        raw = self._request("/0/private/Balance")
        return {k: float(v) for k, v in raw.items()}

    def add_order(
        self,
        pair: str,
        side: str,
        ordertype: str,
        volume: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place an order.
        pair: e.g. XETHZGBP
        side: buy / sell
        ordertype: market / limit
        """
        data: Dict[str, Any] = {
            "pair": pair,
            "type": side,
            "ordertype": ordertype,
            "volume": str(volume),
        }
        if price is not None:
            data["price"] = str(price)
        return self._request("/0/private/AddOrder", data)

    def withdraw(
        self,
        asset: str,
        amount: float,
        key: str,
    ) -> Dict[str, Any]:
        """
        Withdraw to a whitelisted address key.
        asset: e.g. ETH, SOL
        key: the withdrawal address name configured in Kraken UI
        """
        data = {
            "asset": asset,
            "amount": str(amount),
            "key": key,
        }
        return self._request("/0/private/Withdraw", data)

    def get_withdrawal_methods(self, asset: str) -> List[Dict[str, Any]]:
        data = {"asset": asset}
        return self._request("/0/private/WithdrawMethods", data)


class ExchangeClient:
    """
    Generic exchange wrapper. Currently only Kraken is supported.
    Extend here for Binance, Coinbase, etc.
    """

    def __init__(self, backend: str = "kraken"):
        if backend == "kraken":
            self.client = KrakenClient()
        else:
            raise ValueError(f"Exchange backend '{backend}' not supported yet.")

    def get_balance(self) -> Dict[str, float]:
        return self.client.get_balance()

    def buy_market(self, pair: str, volume: float) -> Dict[str, Any]:
        return self.client.add_order(pair, "buy", "market", volume)

    def withdraw(self, asset: str, amount: float, key: str) -> Dict[str, Any]:
        return self.client.withdraw(asset, amount, key)
