import json
from typing import Optional

from src.chain_clients.ethereum_client import EthereumClient
from src.safety_guard import SafetyGuard, SafetyError

LIDO_ADDRESS = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"

LIDO_ABI = json.loads(
    '[{"inputs":[{"internalType":"address","name":"_referral","type":"address"}],"name":"submit","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"_account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"getTotalPooledEther","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":true,"inputs":[],"name":"getTotalShares","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
)


class LidoClient:
    """
    Real Lido Ethereum staking integration.
    Stake ETH -> receive stETH (shares-based yield token).
    stETH uses a shares-based architecture where the exchange rate
    (totalPooledEther / totalShares) updates per Ethereum epoch (~6.4 min).
    balanceOf() returns the increasing balance — no separate harvest needed.
    """

    def __init__(self, client: EthereumClient, guard: Optional[SafetyGuard] = None):
        self.client = client
        self.guard = guard or SafetyGuard()
        self.contract = self.client.w3.eth.contract(
            address=self.client.w3.to_checksum_address(LIDO_ADDRESS),
            abi=LIDO_ABI,
        )

    def get_steth_balance(self) -> float:
        """Return stETH balance in ETH terms."""
        try:
            raw = self.contract.functions.balanceOf(self.client.address).call()
            return float(raw) / 1e18
        except Exception:
            return 0.0

    def submit(self, amount_eth: float, referral: Optional[str] = None) -> str:
        """
        Submit ETH to Lido and receive stETH.
        stETH rebases daily; no separate harvest needed.
        """
        self.guard.check_min_trade_eth(amount_eth)
        ref = self.client.w3.to_checksum_address(referral or self.client.address)
        return self.client.exec_contract_call(
            contract_address=LIDO_ADDRESS,
            abi=LIDO_ABI,
            function_name="submit",
            args=(ref,),
            value_eth=amount_eth,
            gas_limit=200000,
        )

    def unwrap_steth(self, amount_eth: float) -> str:
        """
        Unwrap stETH to ETH via the Lido withdrawal queue
        (not instant — requires request + claim flow).
        For instant access, use Curve/1inch to swap stETH->ETH.
        This method is a placeholder that warns the user.
        """
        raise SafetyError(
            "Lido withdrawals use a request+claim queue (not instant). "
            "To exit quickly, swap stETH → ETH on DEX. Not implemented here."
        )
