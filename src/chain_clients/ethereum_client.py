import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from web3 import Web3
from eth_account import Account
from eth_account.datastructures import HexBytes

from src.safety_guard import SafetyGuard, SafetyError
from src.transaction_monitor import TransactionMonitor, TransactionFailed

ERC20_ABI = json.loads(
    '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
)

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


class EthereumClient:
    """
    Production-grade Ethereum client with gas estimation, EIP-1559
    support, nonce management, and safe transaction broadcast.
    """

    def __init__(
        self,
        rpc_url: str,
        wallet_name: str = "wallet_01",
        guard: Optional[SafetyGuard] = None,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to Ethereum RPC: {rpc_url}")
        self.account = self._load_account(wallet_name)
        self.guard = guard or SafetyGuard()
        self.monitor = TransactionMonitor(self.w3)
        self._nonce_lock = threading.Lock()
        self._cached_nonce: Optional[int] = None

    def _load_account(self, name: str) -> Account:
        env_path = os.path.join("wallets", f"{name}.env")
        key: Optional[str] = os.getenv("PRIVATE_KEY")
        if not key or key == "0x00":
            key = None
            if os.path.isfile(env_path):
                with open(env_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith("PRIVATE_KEY="):
                            key = line.split("=", 1)[1].strip('"').strip("'")
                            break
        if not key or key == "0x00":
            raise ValueError(f"No private key found for wallet '{name}'. Generate one with --generate-wallet")
        return Account.from_key(key)

    @property
    def address(self) -> str:
        return self.account.address

    def get_eth_balance(self) -> float:
        wei = self.w3.eth.get_balance(self.address)
        return float(self.w3.from_wei(wei, "ether"))

    def get_token_balance(self, token_address: str) -> float:
        token = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        decimals = token.functions.decimals().call()
        raw = token.functions.balanceOf(self.address).call()
        return float(raw) / (10 ** decimals)

    def _next_nonce(self) -> int:
        """Return the next safe nonce. Uses a cached counter with lock to prevent races between pending transactions."""
        with self._nonce_lock:
            if self._cached_nonce is not None:
                self._cached_nonce += 1
                return self._cached_nonce
            # First call or after cache reset: fetch from chain (pending-aware)
            self._cached_nonce = self.w3.eth.get_transaction_count(self.address, "pending")
            nonce = self._cached_nonce
            self._cached_nonce += 1
            return nonce

    def _reset_nonce_cache(self) -> None:
        """Reset the nonce cache after an external state change (e.g., confirmed tx from another source)."""
        with self._nonce_lock:
            self._cached_nonce = None

    def _build_gas_params(self) -> Dict[str, int]:
        """Build EIP-1559 fee params or legacy gasPrice."""
        try:
            base_fee = self.w3.eth.get_block("latest")["baseFeePerGas"]
            max_priority = self.w3.to_wei(self.guard.get("MAX_PRIORITY_GWEI"), "gwei")
            max_fee = base_fee * 2 + max_priority
            return {
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": max_priority,
            }
        except Exception:
            # Fallback to legacy
            gas_price = self.w3.eth.gas_price
            self.guard.check_gas_price(float(self.w3.from_wei(gas_price, "gwei")))
            return {"gasPrice": gas_price}

    def exec_contract_call(
        self,
        contract_address: str,
        abi: List[Dict[str, Any]],
        function_name: str,
        args: tuple = (),
        value_eth: float = 0.0,
        gas_limit: Optional[int] = None,
    ) -> str:
        """
        Build, sign, and send a contract call. Returns tx hash.
        """
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(contract_address), abi=abi
        )
        func = contract.functions[function_name](*args)

        tx_params: Dict[str, Any] = {
            "from": self.address,
            "nonce": self._next_nonce(),
            "chainId": self.w3.eth.chain_id,
            **self._build_gas_params(),
        }
        if value_eth > 0:
            tx_params["value"] = self.w3.to_wei(value_eth, "ether")

        # Estimate gas if limit not provided
        if gas_limit is None:
            try:
                gas_limit = func.estimate_gas(tx_params) + 50000  # buffer
            except Exception as exc:
                raise SafetyError(f"Gas estimation failed: {exc}")
        tx_params["gas"] = gas_limit

        # Check gas price safety
        if "gasPrice" in tx_params:
            gwei = float(self.w3.from_wei(tx_params["gasPrice"], "gwei"))
            self.guard.check_gas_price(gwei)

        built = func.build_transaction(tx_params)

        # AI sanitisation of on-chain transaction
        from src.ai_sanitizer import get_ai_sanitizer
        ai_check = get_ai_sanitizer().sanitise_transaction(
            action=function_name,
            protocol="ethereum",
            chain="ethereum",
            amount=value_eth,
            contract_address=contract_address,
            extra={"gas_limit": gas_limit},
        )
        if not ai_check.is_safe:
            raise SafetyError(f"AI safety check failed: {ai_check.warnings}")
        for w in ai_check.warnings:
            print(f"[AI WARNING] {w}")

        if self.guard.is_dry_run():
            print(f"[DRY RUN] Would send tx to {contract_address}.{function_name}")
            print(f"  Params: {built}")
            return "0xDRYRUN"

        details = (
            f"Contract: {contract_address}\n"
            f"Function: {function_name}{args}\n"
            f"Value: {value_eth} ETH\n"
            f"Gas limit: {gas_limit}\n"
            f"Nonce: {built['nonce']}"
        )
        if not self.guard.confirm("Contract Call", details):
            raise SafetyError("User aborted contract call.")

        signed = self.account.sign_transaction(built)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        hex_hash = self.w3.to_hex(tx_hash)
        print(f"  Tx broadcast: {hex_hash}")
        receipt = self.monitor.wait_for_receipt(hex_hash)
        print(
            f"  Mined in block {receipt['blockNumber']}. Gas used: {receipt['gasUsed']}"
        )
        return hex_hash

    def transfer_eth(self, to: str, amount_eth: float) -> str:
        """Send ETH to an address."""
        tx = {
            "to": self.w3.to_checksum_address(to),
            "value": self.w3.to_wei(amount_eth, "ether"),
            "from": self.address,
            "nonce": self._next_nonce(),
            "gas": 21000,
            "chainId": self.w3.eth.chain_id,
            **self._build_gas_params(),
        }
        if "gasPrice" in tx:
            self.guard.check_gas_price(float(self.w3.from_wei(tx["gasPrice"], "gwei")))

        if self.guard.is_dry_run():
            print(f"[DRY RUN] Would send {amount_eth} ETH to {to}")
            return "0xDRYRUN"

        if not self.guard.confirm(
            "ETH Transfer", f"Send {amount_eth} ETH to {to}?"
        ):
            raise SafetyError("User aborted transfer.")

        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        hex_hash = self.w3.to_hex(tx_hash)
        self.monitor.wait_for_receipt(hex_hash)
        return hex_hash

    def approve_erc20(
        self, token_address: str, spender: str, amount_raw: int
    ) -> str:
        """Approve a spender for an ERC-20 amount."""
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        tx = contract.functions.approve(
            self.w3.to_checksum_address(spender), amount_raw
        ).build_transaction(
            {
                "from": self.address,
                "nonce": self._next_nonce(),
                "gas": 100000,
                "chainId": self.w3.eth.chain_id,
                **self._build_gas_params(),
            }
        )
        if self.guard.is_dry_run():
            print(f"[DRY RUN] Would approve {spender} for token {token_address}")
            return "0xDRYRUN"
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        hex_hash = self.w3.to_hex(tx_hash)
        self.monitor.wait_for_receipt(hex_hash)
        return hex_hash
