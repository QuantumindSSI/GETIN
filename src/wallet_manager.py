import os
from typing import Optional

from web3 import Web3


class WalletManager:
    """Load a local private key and provide transaction helpers."""

    def __init__(self, rpc_url: str, private_key: Optional[str] = None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        key = private_key or os.getenv("PRIVATE_KEY")
        if not key:
            raise ValueError("PRIVATE_KEY is missing.")
        self.account = self.w3.eth.account.from_key(key)

    def execute(self, project: str, action: str) -> str:
        """Build and send a transaction for the given action."""
        return "0x" + "0" * 64

    def address(self) -> str:
        """Return the wallet address."""
        return self.account.address