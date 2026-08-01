import json
from typing import Any, Dict, Optional

from src.chain_clients.ethereum_client import EthereumClient
from src.safety_guard import SafetyGuard, SafetyError

AAVE_POOL_PROXY = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
AAVE_POOL_DATA_PROVIDER = "0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3"

AAVE_POOL_ABI = json.loads(
    '[{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"onBehalfOf","type":"address"},{"internalType":"uint16","name":"referralCode","type":"uint16"}],"name":"supply","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"},{"internalType":"address","name":"to","type":"address"}],"name":"withdraw","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"getUserAccountData","outputs":[{"internalType":"uint256","name":"totalCollateralBase","type":"uint256"},{"internalType":"uint256","name":"totalDebtBase","type":"uint256"},{"internalType":"uint256","name":"availableBorrowsBase","type":"uint256"},{"internalType":"uint256","name":"currentLiquidationThreshold","type":"uint256"},{"internalType":"uint256","name":"ltv","type":"uint256"},{"internalType":"uint256","name":"healthFactor","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"asset","type":"address"}],"name":"getReserveData","outputs":[{"internalType":"uint256","name":"unbacked","type":"uint256"},{"internalType":"uint256","name":"accruedToTreasuryShares","type":"uint256"},{"internalType":"uint256","name":"totalAToken","type":"uint256"},{"internalType":"uint256","name":"totalStableDebt","type":"uint256"},{"internalType":"uint256","name":"totalVariableDebt","type":"uint256"},{"internalType":"uint256","name":"liquidityRate","type":"uint256"},{"internalType":"uint256","name":"variableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"stableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"averageStableBorrowRate","type":"uint256"},{"internalType":"uint256","name":"liquidityIndex","type":"uint256"},{"internalType":"uint256","name":"variableBorrowIndex","type":"uint256"},{"internalType":"uint40","name":"lastUpdateTimestamp","type":"uint40"}],"stateMutability":"view","type":"function"}]'
)

ERC20_ABI_MINIMAL = json.loads(
    '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]'
)


class AaveV3Client:
    """
    Real Aave v3 mainnet integration for Ethereum.
    Supports supply (deposit), withdraw, and health check.
    """

    def __init__(self, client: EthereumClient, guard: Optional[SafetyGuard] = None):
        self.client = client
        self.guard = guard or SafetyGuard()
        self.pool = self.client.w3.eth.contract(
            address=self.client.w3.to_checksum_address(AAVE_POOL_PROXY),
            abi=AAVE_POOL_ABI,
        )

    def get_reserve_data(self, asset: str) -> Dict[str, Any]:
        data = self.pool.functions.getReserveData(
            self.client.w3.to_checksum_address(asset)
        ).call()
        return {
            "liquidityRate": data[5],
            "variableBorrowRate": data[6],
        }

    def get_user_account_data(self) -> Dict[str, Any]:
        data = self.pool.functions.getUserAccountData(self.client.address).call()
        return {
            "totalCollateralBase": data[0],
            "totalDebtBase": data[1],
            "availableBorrowsBase": data[2],
            "currentLiquidationThreshold": data[3],
            "ltv": data[4],
            "healthFactor": data[5],
        }

    def supply(self, asset: str, amount_human: float) -> str:
        """
        Deposit an ERC-20 into Aave v3.
        For ETH, wrap to WETH first.
        """
        asset_checksum = self.client.w3.to_checksum_address(asset)
        token = self.client.w3.eth.contract(address=asset_checksum, abi=ERC20_ABI_MINIMAL)
        decimals = token.functions.decimals().call()
        amount_raw = int(amount_human * (10 ** decimals))

        # Approve Aave Pool to pull tokens
        allowance = token.functions.allowance(self.client.address, AAVE_POOL_PROXY).call()
        if allowance < amount_raw:
            self.client.approve_erc20(asset, AAVE_POOL_PROXY, amount_raw)

        self.guard.check_min_trade_eth(amount_human)

        return self.client.exec_contract_call(
            contract_address=AAVE_POOL_PROXY,
            abi=AAVE_POOL_ABI,
            function_name="supply",
            args=(asset_checksum, amount_raw, self.client.address, 0),
            value_eth=0.0,
            gas_limit=400000,
        )

    def withdraw(self, asset: str, amount_human: float) -> str:
        """Withdraw an asset from Aave v3."""
        asset_checksum = self.client.w3.to_checksum_address(asset)
        token = self.client.w3.eth.contract(address=asset_checksum, abi=ERC20_ABI_MINIMAL)
        decimals = token.functions.decimals().call()
        amount_raw = int(amount_human * (10 ** decimals))

        return self.client.exec_contract_call(
            contract_address=AAVE_POOL_PROXY,
            abi=AAVE_POOL_ABI,
            function_name="withdraw",
            args=(asset_checksum, amount_raw, self.client.address),
            value_eth=0.0,
            gas_limit=400000,
        )

    def withdraw_all(self, asset: str) -> str:
        """Withdraw the entire balance of an asset."""
        asset_checksum = self.client.w3.to_checksum_address(asset)
        # max_uint256 signals "withdraw all"
        max_uint = 2**256 - 1
        return self.client.exec_contract_call(
            contract_address=AAVE_POOL_PROXY,
            abi=AAVE_POOL_ABI,
            function_name="withdraw",
            args=(asset_checksum, max_uint, self.client.address),
            value_eth=0.0,
            gas_limit=400000,
        )

    def get_a_token_balance(self, a_token_address: str) -> float:
        """Return aToken balance for a given aToken contract."""
        return self.client.get_token_balance(a_token_address)
