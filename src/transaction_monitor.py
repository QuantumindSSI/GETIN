import time
from typing import Any, Dict, Optional

from web3 import Web3
from web3.exceptions import TransactionNotFound, TimeExhausted


class TransactionMonitor:
    """
    Wait for Ethereum transaction receipts, detect failures,
    and provide retry guidance.
    """

    def __init__(self, w3: Web3):
        self.w3 = w3

    def wait_for_receipt(
        self,
        tx_hash: str,
        confirmations: int = 1,
        timeout: int = 180,
        poll_latency: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Poll for a transaction receipt until mined or timeout.
        Returns the receipt dict or raises on failure.
        """
        start = time.time()
        receipt: Optional[Dict[str, Any]] = None
        while time.time() - start < timeout:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    break
            except TransactionNotFound:
                pass
            time.sleep(poll_latency)

        if receipt is None:
            raise TimeExhausted(
                f"Transaction {tx_hash} not mined within {timeout}s"
            )

        block_number = receipt["blockNumber"]
        if confirmations > 1:
            while True:
                latest = self.w3.eth.block_number
                if latest - block_number >= confirmations - 1:
                    break
                if time.time() - start > timeout:
                    raise TimeExhausted(
                        f"Transaction {tx_hash} did not reach {confirmations} confirmations in time"
                    )
                time.sleep(poll_latency)

        if receipt.get("status") != 1:
            raise TransactionFailed(
                f"Transaction {tx_hash} failed (status 0). "
                f"Gas used: {receipt.get('gasUsed')}."
            )

        return receipt

    def get_tx_link(self, tx_hash: str, chain_id: int) -> str:
        if chain_id == 1:
            return f"https://etherscan.io/tx/{tx_hash}"
        if chain_id == 137:
            return f"https://polygonscan.com/tx/{tx_hash}"
        if chain_id == 42161:
            return f"https://arbiscan.io/tx/{tx_hash}"
        if chain_id == 10:
            return f"https://optimistic.etherscan.io/tx/{tx_hash}"
        return tx_hash


class TransactionFailed(Exception):
    pass
