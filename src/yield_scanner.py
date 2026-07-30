from typing import Any, Dict, List, Optional

import requests

DEFILLAMA_POOLS = "https://yields.llama.fi/pools"

TARGET_SLUGS = [
    ("Aave v3 ETH",      "aave-v3",      "Ethereum", "WETH"),
    ("Aave v3 USDC",     "aave-v3",      "Ethereum", "USDC"),
    ("Compound v3 USDC", "compound-v3",  "Ethereum", "USDC"),
    ("Lido stETH",       "lido",         "Ethereum", "STETH"),
    ("Rocket Pool rETH", "rocket-pool",  "Ethereum", "RETH"),
    ("Frax sfrxETH",     "frax-ether",   "Ethereum", "SFRXETH"),
    ("Uniswap ETH/USDC", "uniswap-v3",   "Ethereum", "USDC-WETH"),
    ("Curve 3pool",      "curve-dex",    "Ethereum", "DAI-USDC-USDT"),
    ("Yearn USDC",       "yearn-finance","Ethereum", "USDC"),
    ("Yearn ETH",        "yearn-finance","Ethereum", "WETH"),
    # Solana DeFi
    ("JitoSOL (Solana)",      "jito-liquid-staking",    "Solana", "JITOSOL"),
    ("Marinade mSOL (Solana)","marinade-liquid-staking","Solana", "MSOL"),
    ("Kamino Lend SOL",       "kamino-lend",            "Solana", "SOL"),
    ("Kamino Lend USDC",      "kamino-lend",            "Solana", "USDC"),
    ("Orca SOL/USDC LP",      "orca-dex",               "Solana", "SOL-USDC"),
    ("Drift dSOL (Solana)",   "drift-staked-sol",       "Solana", "DSOL"),
    ("Marginfi LST (Solana)", "marginfi-lst",           "Solana", "LST"),
]


class YieldScanner:
    """Scan live DeFi yields from the DefiLlama API."""

    def __init__(self):
        self.session = requests.Session()

    def _fetch_pools(self) -> List[Dict[str, Any]]:
        """Download all pools from DefiLlama."""
        resp = self.session.get(DEFILLAMA_POOLS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def scan(self) -> List[Dict[str, Any]]:
        """Return live yield entries for tracked protocols."""
        try:
            pools = self._fetch_pools()
        except Exception:
            return []

        index = {}
        for pool in pools:
            key = (pool.get("project", ""), pool.get("chain", ""), pool.get("symbol", ""))
            index[key] = pool

        results: List[Dict[str, Any]] = []
        for label, slug, chain, symbol in TARGET_SLUGS:
            pool = index.get((slug, chain, symbol))
            if pool is None:
                results.append({
                    "label": label, "asset": "N/A", "apy": 0, "tvl": 0,
                })
                continue
            results.append({
                "label": label,
                "asset": symbol,
                "apy": float(pool.get("apy", 0) or 0),
                "tvl": float(pool.get("tvlUsd", 0) or 0),
            })
        return results

    @staticmethod
    def calculate_roi(apy: float, amount: float = 1000.0) -> Dict[str, Any]:
        """Project per-6-hour and 30-day returns for a given APY."""
        hourly_rate = apy / 100.0 / 365.0 / 24.0
        per_6h = amount * hourly_rate * 6.0
        per_30d = amount * hourly_rate * 24.0 * 30.0
        return {
            "amount_usd": round(amount, 2),
            "apy_pct": round(apy, 2),
            "roi_6h_usd": round(per_6h, 4),
            "roi_6h_pct": round(per_6h / amount * 100, 6),
            "roi_30d_usd": round(per_30d, 2),
            "roi_30d_pct": round(per_30d / amount * 100, 4),
        }