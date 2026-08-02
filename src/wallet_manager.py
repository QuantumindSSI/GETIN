from typing import Any, Dict, List, Optional, Tuple

from src.chain_clients.ethereum_client import EthereumClient
from src.chain_clients.solana_client import SolanaClient
from src.safety_guard import SafetyGuard, SafetyError
from src.yield_protocols.aave_v3 import AaveV3Client
from src.yield_protocols.lido import LidoClient


class WalletManager:
    """
    Unified wallet interface that routes actions to Ethereum or Solana
    chain clients. Replaces the previous stub with real transaction execution.
    """

    def __init__(
        self,
        eth_rpc: Optional[str] = None,
        sol_rpc: Optional[str] = None,
        wallet_name: str = "wallet_01",
        sol_wallet_name: Optional[str] = None,
        guard: Optional[SafetyGuard] = None,
    ):
        self.guard = guard or SafetyGuard()
        self.eth_client: Optional[EthereumClient] = None
        self.sol_client: Optional[SolanaClient] = None

        if eth_rpc:
            try:
                self.eth_client = EthereumClient(eth_rpc, wallet_name, guard=self.guard)
            except Exception:
                pass

        sol_name = sol_wallet_name or wallet_name
        if sol_rpc:
            try:
                self.sol_client = SolanaClient(sol_rpc, sol_name, guard=self.guard)
            except Exception:
                pass

        self.wallet_name = wallet_name
        self.sol_wallet_name = sol_name

    @property
    def eth_address(self) -> Optional[str]:
        return self.eth_client.address if self.eth_client else None

    @property
    def sol_address(self) -> Optional[str]:
        return self.sol_client.address if self.sol_client else None

    @property
    def addresses(self) -> Dict[str, Optional[str]]:
        return {"ethereum": self.eth_address, "solana": self.sol_address}

    def get_eth_balance(self) -> float:
        if not self.eth_client:
            return 0.0
        return self.eth_client.get_eth_balance()

    def get_sol_balance(self) -> float:
        if not self.sol_client:
            return 0.0
        return self.sol_client.get_balance()

    def execute(self, project: str, action: str) -> str:
        """
        Execute an on-chain action for a given project.
        This is used by the legacy task_scheduler and now routes to real clients.
        """
        print(f"Executing {action} for {project}...")
        if self.guard.is_dry_run():
            print(f"[DRY RUN] Would execute {action} on {project}")
            return "0xDRYRUN"

        try:
            if project.lower() in ("lido", "steth"):
                if not self.eth_client:
                    raise SafetyError("No Ethereum client available for Lido")
                lido = LidoClient(self.eth_client, self.guard)
                if action == "stake":
                    bal = self.eth_client.get_eth_balance()
                    if bal < 0.001:
                        raise SafetyError("Insufficient ETH to stake")
                    return lido.submit(bal * 0.99)  # keep some for gas
                elif action == "balance":
                    bal = lido.get_steth_balance()
                    print(f"  stETH balance: {bal}")
                    return f"balance:{bal}"

            elif project.lower() in ("aave", "aave_v3"):
                if not self.eth_client:
                    raise SafetyError("No Ethereum client available for Aave")
                aave = AaveV3Client(self.eth_client, self.guard)
                if action == "deposit_weth":
                    # Deposit WETH if present; otherwise requires wrap first
                    weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
                    bal = self.eth_client.get_token_balance(weth)
                    if bal > 0:
                        return aave.supply(weth, bal)
                    raise SafetyError("No WETH balance to supply")
                elif action == "withdraw_weth":
                    weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
                    return aave.withdraw_all(weth)
                elif action == "health":
                    data = aave.get_user_account_data()
                    print(f"  Health factor: {data['healthFactor'] / 1e18}")
                    return f"health:{data['healthFactor']}"

            elif project.lower() in ("jito", "jitosol", "solana"):
                if not self.sol_client:
                    raise SafetyError("No Solana client available")
                from src.yield_protocols.jupiter_solana import JupiterSwap
                jupiter = JupiterSwap(self.sol_client, self.guard)
                if action == "stake":
                    bal = self.sol_client.get_balance()
                    if bal < 0.01:
                        raise SafetyError("Insufficient SOL to stake")
                    result = jupiter.swap_sol_to_token(
                        "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
                        bal * 0.98,
                    )
                    return result["tx"]
                elif action == "unstake":
                    bal = self.sol_client.get_token_balance(
                        "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"
                    )
                    if bal <= 0:
                        raise SafetyError("No JitoSOL to unstake")
                    result = jupiter.swap_token_to_sol(
                        "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
                        int(bal * 1e9),
                    )
                    return result["tx"]

            else:
                raise SafetyError(f"Unknown project/action: {project}/{action}")

        except Exception as exc:
            print(f"  Action failed: {exc}")
            return f"error:{exc}"

    def address(self) -> str:
        return self.eth_address or self.sol_address or ""

    def all_addresses(self) -> List[Tuple[str, str]]:
        result: List[Tuple[str, str]] = []
        if self.eth_address:
            result.append(("ethereum", self.eth_address))
        if self.sol_address:
            result.append(("solana", self.sol_address))
        return result
