import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from web3 import Web3

# Testnet RPC endpoints and chain IDs
# WARNING: These are testnet networks only. Testnet tokens have NO real value.
# The auto-farmer is a development/testing tool, not a production yield farm.
# All contract addresses below are PLACEHOLDER DUMMIES.
# Real on-chain staking/swapping requires verified production contract addresses
# and should NEVER be used with user funds without explicit, informed consent.

TESTNETS = {
    "monad": {
        "rpc": "https://testnet-rpc.monad.xyz",
        "chain_id": 10143,
        "symbol": "MON",
    },
    "berachain": {
        "rpc": "https://bartio.rpc.berachain.com/",
        "chain_id": 80084,
        "symbol": "BERA",
    },
    "somnia": {
        "rpc": "https://api.infra.testnet.somnia.network/",
        "chain_id": 50312,
        "symbol": "STT",
    },
}

WARNING_DUMMY_ADDRESSES = """
WARNING: All contract addresses below are PLACEHOLDER DUMMIES.
- Router addresses are from Ethereum mainnet, NOT the testnet chain.
- Staking contracts use sequential dummy addresses.
- Wrapped native token addresses are from other chains.

Transactions sent to dummy addresses WILL FAIL.
This is a DEVELOPMENT TOOL, not tested for production use.
"""

# DEX router addresses — ALL ARE DUMMIES. Do NOT use with real funds.
# To use this module: replace with verified router addresses from
# the official Monad, Berachain, and Somnia documentation.
ROUTERS = {
    "monad": {
        "uniswap": "0x000000000000000000000000000000000000DEAD",
        "pancakeswap": "0x000000000000000000000000000000000000DEAD",
        "izumi": "0x000000000000000000000000000000000000DEAD",
    },
    "berachain": {
        "bex": "0x000000000000000000000000000000000000DEAD",
        "kodiak": "0x000000000000000000000000000000000000DEAD",
    },
    "somnia": {
        "stargate": "0x000000000000000000000000000000000000DEAD",
    },
}

# Minimal ERC-20 ABI for approve + swap (testing only)
ERC20_ABI = [
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

UNISWAP_ROUTER_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "amountOutMin", "type": "uint256"}, {"internalType": "address[]", "name": "path", "type": "address[]"}, {"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "deadline", "type": "uint256"}], "name": "swapExactETHForTokens", "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "stateMutability": "payable", "type": "function"},
]

WRAPPED_NATIVE = {
    "monad": "0x000000000000000000000000000000000000DEAD",
    "berachain": "0x000000000000000000000000000000000000DEAD",
    "somnia": "0x000000000000000000000000000000000000DEAD",
}


class OnchainAutoFarmer:
    """
    DEVELOPMENT TOOL: Automate testnet on-chain actions for testing.
    ALL contract addresses are DUMMIES. Do not use with real funds.
    This module is intended for development testing across Monad, Berachain,
    and Somnia testnets only.

    To make this production-ready: replace ALL addresses in ROUTERS,
    WRAPPED_NATIVE, and the staking_contracts dict in stake() with verified
    production contract addresses from the official protocol documentation.

    Additionally, review the Aave, Lido, and Jupiter modules in
    src/yield_protocols/ for production-grade mainnet staking.
    """

    def __init__(self, private_key: Optional[str] = None):
        key = private_key or os.getenv("PRIVATE_KEY")
        if not key:
            raise ValueError("PRIVATE_KEY is missing. Set it in .env")
        self.private_key = key
        self.connections: Dict[str, Web3] = {}

    def _connect(self, network: str) -> Web3:
        if network not in self.connections:
            cfg = TESTNETS[network]
            w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
            if not w3.is_connected():
                raise ConnectionError(f"Cannot connect to {network} RPC: {cfg['rpc']}")
            self.connections[network] = w3
        return self.connections[network]

    def _account(self, w3: Web3) -> Any:
        return w3.eth.account.from_key(self.private_key)

    def faucet_claim(self, network: str) -> str:
        """
        Attempt faucet claim via HTTP.
        WARNING: Most testnet faucets require CAPTCHA, Twitter/Discord verification,
        and human interaction. Automated HTTP requests will likely fail.
        """
        faucets = {
            "monad": [
                ("https://testnet.monad.xyz/", "GET"),
                ("https://faucet.quicknode.com/monad/testnet", "POST"),
            ],
            "berachain": [
                ("https://bartio.faucet.berachain.com/", "GET"),
            ],
            "somnia": [
                ("https://testnet.somnia.network/", "GET"),
            ],
        }
        import requests
        w3 = self._connect(network)
        addr = self._account(w3).address
        for url, method in faucets.get(network, []):
            try:
                resp = requests.request(method, url, json={"address": addr}, timeout=15)
                if resp.status_code == 200:
                    return f"Faucet claim sent to {url.split('/')[2]}"
            except Exception:
                continue
        return "All faucets unavailable or rate-limited. Faucets typically require manual CAPTCHA solving — use the web UI directly."

    def swap(self, network: str) -> Optional[str]:
        """
        Attempt swap on a testnet DEX.
        WARNING: Router addresses are DUMMIES. Swap will FAIL.
        This is a development stub — not tested with real testnet routers.
        """
        return None  # Stub — routers are dummy addresses, swaps will fail.

    def stake(self, network: str) -> Optional[str]:
        """
        Attempt staking on a testnet.
        WARNING: Staking contract addresses are DUMMIES. Stake will FAIL.
        For real staking, use the Aave, Lido, or Jupiter modules in src/yield_protocols/.
        """
        return None  # Stub — staking contracts are dummy addresses.

    def deploy_contract(self, network: str) -> Optional[str]:
        """Deploy a minimal contract to a testnet (development testing only)."""
        bytecode = "0x6080604052348015600e575f80fd5b50603e80601a5f395ff3fe60806040525f80fdfea2646970667358221220000000000000000000000000000000000000000000000000000000000000000064736f6c63430008180033"
        w3 = self._connect(network)
        acct = self._account(w3)
        try:
            nonce = w3.eth.get_transaction_count(acct.address)
            tx = {
                "from": acct.address,
                "to": None,
                "data": bytecode,
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
                "chainId": TESTNETS[network]["chain_id"],
            }
            signed = acct.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            return w3.to_hex(tx_hash)
        except Exception:
            return None

    def run_rotation(self, network: str, actions_per_cycle: int = 3) -> List[Dict]:
        """
        Execute a cycle of testnet actions.
        WARNING: swap() and stake() are stubs — they always return None.
        Only deploy_contract() may succeed if the RPC is reachable.
        """
        results = []
        try:
            # Only deploy_contract is functional; swap/stake use dummy addresses
            tx_hash = self.deploy_contract(network)
            results.append({
                "network": network,
                "action": "deploy_contract",
                "tx_hash": tx_hash,
                "ok": tx_hash is not None,
                "note": "Only contract deployment is tested. Swap and stake use dummy addresses.",
            })
        except Exception as e:
            results.append({"network": network, "action": "deploy_contract", "error": str(e), "ok": False})
        return results

    def run_all_testnets(self, actions_per_cycle: int = 2) -> Dict[str, List[Dict]]:
        """
        Run testnet rotation.
        WARNING: All contract interaction addresses are DUMMIES.
        Only contract deployment bytecode uses real compiled Solidity.
        Aave, Lido, and Jupiter modules provide production-grade staking.
        """
        all_results = {}
        for network in ["monad", "berachain", "somnia"]:
            try:
                all_results[network] = self.run_rotation(network, actions_per_cycle)
            except Exception as e:
                all_results[network] = [{"network": network, "action": "connect", "error": str(e), "ok": False}]
            time.sleep(random.randint(20, 60))
        return all_results