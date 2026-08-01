import base64
import httpx
from typing import Any, Dict, Optional

from solders.transaction import VersionedTransaction

from src.chain_clients.solana_client import SolanaClient
from src.safety_guard import SafetyGuard, SafetyError

JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6"


class JupiterSwap:
    """
    Swap any SPL token via Jupiter Aggregator v6.
    Primary use-case: SOL → JitoSOL / mSOL for yield farming.
    """

    def __init__(self, client: SolanaClient, guard: Optional[SafetyGuard] = None):
        self.client = client
        self.guard = guard or SafetyGuard()
        self.http = httpx.Client(timeout=30.0)

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount_lamports: int,
        slippage_bps: int = 50,
    ) -> Dict[str, Any]:
        """Fetch a Jupiter quote."""
        self.guard.check_slippage(slippage_bps)
        url = (
            f"{JUPITER_QUOTE_API}/quote"
            f"?inputMint={input_mint}"
            f"&outputMint={output_mint}"
            f"&amount={amount_lamports}"
            f"&slippageBps={slippage_bps}"
            f"&onlyDirectRoutes=false"
        )
        resp = self.http.get(url)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise SafetyError(f"Jupiter quote error: {data['error']}")
        return data

    def execute_swap(self, quote: Dict[str, Any], wrap_unwrap_sol: bool = True) -> str:
        """
        Request a signed transaction from Jupiter and broadcast it.
        Returns the swap transaction signature.
        """
        swap_url = f"{JUPITER_QUOTE_API}/swap"
        payload = {
            "quoteResponse": quote,
            "userPublicKey": self.client.address,
            "wrapAndUnwrapSol": wrap_unwrap_sol,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": "auto",
        }
        resp = self.http.post(swap_url, json=payload)
        resp.raise_for_status()
        swap_data = resp.json()
        if "error" in swap_data:
            raise SafetyError(f"Jupiter swap error: {swap_data['error']}")

        raw_tx = swap_data["swapTransaction"]
        tx_bytes = base64.b64decode(raw_tx)
        swap_tx = VersionedTransaction.from_bytes(tx_bytes)

        # Sign with our keypair
        signed_tx = VersionedTransaction(swap_tx.message, [self.client.keypair])

        if self.guard.is_dry_run():
            print("[DRY RUN] Would execute Jupiter swap tx")
            return "DRYRUN"

        sig = self.client.rpc.send_transaction(signed_tx)
        self.client.rpc.confirm_transaction(sig)
        return sig

    def swap_sol_to_token(self, token_mint: str, amount_sol: float, slippage_bps: int = 50) -> Dict[str, Any]:
        """
        Convenience wrapper: swap native SOL to any output token.
        Returns result dict with tx signature and output amount.
        """
        self.guard.check_min_trade_sol(amount_sol)
        lamports = int(amount_sol * 1e9)
        quote = self.get_quote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint=token_mint,
            amount_lamports=lamports,
            slippage_bps=slippage_bps,
        )
        out_amount = int(quote.get("outAmount", 0))
        price_impact = float(quote.get("priceImpactPct", 0))
        print(f"  Jupiter quote: {amount_sol} SOL -> {out_amount} units (impact {price_impact}%)")

        # Ensure output ATA exists before swapping
        self.client.ensure_associated_token_account(token_mint)

        sig = self.execute_swap(quote)
        return {
            "tx": sig,
            "input_sol": amount_sol,
            "output_raw": out_amount,
            "price_impact_pct": price_impact,
            "output_mint": token_mint,
        }

    def swap_token_to_sol(self, token_mint: str, amount_token_raw: int, slippage_bps: int = 50) -> Dict[str, Any]:
        """Swap any token back to native SOL."""
        quote = self.get_quote(
            input_mint=token_mint,
            output_mint="So11111111111111111111111111111111111111112",
            amount_lamports=amount_token_raw,
            slippage_bps=slippage_bps,
        )
        out_amount = int(quote.get("outAmount", 0))
        sig = self.execute_swap(quote)
        return {
            "tx": sig,
            "input_raw": amount_token_raw,
            "output_sol": out_amount / 1e9,
            "output_mint": token_mint,
        }
