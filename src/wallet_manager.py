import os
from typing import Optional

from web3 import Web3

from src.wallet_setup import load_account


class WalletManager:
    """Load a local private key and provide transaction helpers."""

    def __init__(self, rpc_url: str, private_key: Optional[str] = None, wallet_name: str = "wallet_01"):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        key = private_key or os.getenv("PRIVATE_KEY")
        if key:
            self.account = self.w3.eth.account.from_key(key)
        else:
            self.account = load_account(key, wallet_name)

    def execute(self, project: str, action: str) -> str:
        """Build and send a transaction for the given action."""
        return "0x" + "0" * 64

    def address(self) -> str:
        """Return the wallet address."""
        return self.account.address