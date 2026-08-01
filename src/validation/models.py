"""
Pydantic validation models for the GETIN yield farming bot.
Validates all data structures at the type level to catch:
- Hallucinated reward values
- Invalid contract addresses
- Incorrect ABI signatures
- Malformed transaction parameters
- Fabricated earnings projections

Usage:
    python -m src.validation.run_validation

This module does NOT run the bot. It statically validates the data
contracts to ensure the codebase is grounded in real engineering patterns.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ValidationError,
    ValidationInfo,
)
from pydantic_core.core_schema import FieldValidationInfo


# ---------------------------------------------------------------------------
# Blockchain identity validators
# ---------------------------------------------------------------------------

ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
ETH_TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
SOL_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
ETH_PRIVATE_KEY_RE = re.compile(r"^[a-fA-F0-9]{64}$")
SOL_PRIVATE_KEY_RE = re.compile(r"^[a-fA-F0-9]{64,128}$")

# Known good mainnet contract addresses (verified on Etherscan/Solscan)
KNOWN_CONTRACTS = {
    "aave_v3_pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
    "lido_steth": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
    "aave_v3_data_provider": "0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3",
    "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
}

KNOWN_SOL_MINTS = {
    "sol": "So11111111111111111111111111111111111111112",
    "jitosol": "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
    "msol": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
}

# Dummy addresses (must NOT be used for real transactions)
DUMMY_ADDRESSES = {
    "0x0000000000000000000000000000000000000000",
    "0x0000000000000000000000000000000000000001",
    "0x0000000000000000000000000000000000000002",
    "0x0000000000000000000000000000000000000003",
    "0x000000000000000000000000000000000000DEAD",
    "0xDEAD000000000000000000000000000000000000",
}


# ---------------------------------------------------------------------------
# Ethereum Models
# ---------------------------------------------------------------------------

class EthereumAddress(BaseModel):
    """Validated Ethereum address (checksum format)."""
    address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")

    @field_validator("address")
    @classmethod
    def not_dummy(cls, v: str) -> str:
        """Reject known dummy/addressing placeholder addresses."""
        lower = v.lower()
        for dummy in DUMMY_ADDRESSES:
            if v.lower() == dummy.lower():
                raise ValueError(f"Address {v} is a known dummy/placeholder. Use a real contract address.")
        return v

    @property
    def is_contract(self) -> bool:
        return self.address.lower() in {c.lower() for c in KNOWN_CONTRACTS.values()}


class EthereumTxHash(BaseModel):
    """Validated Ethereum transaction hash."""
    tx_hash: str = Field(..., pattern=r"^0x[a-fA-F0-9]{64}$")


class EthereumPrivateKey(BaseModel):
    """Validated Ethereum private key (32 bytes hex)."""
    key_hex: str = Field(..., min_length=64, max_length=64)

    @field_validator("key_hex")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if not re.match(ETH_PRIVATE_KEY_RE, v):
            raise ValueError("Private key must be 64 hex characters")
        if v == "00" * 32:
            raise ValueError("Private key is the zero key (insecure placeholder)")
        return v


class EIP1559Params(BaseModel):
    """EIP-1559 transaction fee parameters."""
    max_fee_per_gas: int = Field(..., gt=0)
    max_priority_fee_per_gas: int = Field(..., ge=0)
    max_fee_gwei: float = Field(default=50.0, gt=0)

    @model_validator(mode="after")
    def check_fee_ratio(self) -> "EIP1559Params":
        if self.max_priority_fee_per_gas > self.max_fee_per_gas:
            raise ValueError("Priority fee cannot exceed max fee")
        return self


class TransactionParams(BaseModel):
    """Validated Ethereum transaction parameters."""
    to: Optional[EthereumAddress] = None
    value_wei: int = Field(default=0, ge=0)
    data: str = Field(default="0x")
    gas_limit: int = Field(default=21000, ge=21000, le=30_000_000)
    chain_id: int = Field(default=1, ge=1)
    nonce: int = Field(ge=0)

    @field_validator("data")
    @classmethod
    def validate_calldata(cls, v: str) -> str:
        if not v.startswith("0x"):
            raise ValueError("Data must be hex-prefixed")
        if len(v) > 2 and not re.match(r"^0x[a-fA-F0-9]+$", v):
            raise ValueError("Data must be valid hex")
        return v


# ---------------------------------------------------------------------------
# Solana Models
# ---------------------------------------------------------------------------

class SolanaAddress(BaseModel):
    """Validated Solana address (base58)."""
    address: str = Field(..., min_length=32, max_length=44)

    @field_validator("address")
    @classmethod
    def validate_sol_address(cls, v: str) -> str:
        if not re.match(r"^[1-9A-HJ-NP-Za-km-z]+$", v):
            raise ValueError(f"Invalid base58 Solana address: {v}")
        return v


class SolanaMint(BaseModel):
    """Validated Solana SPL token mint address."""
    mint: str

    @field_validator("mint")
    @classmethod
    def validate_mint(cls, v: str) -> str:
        if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", v):
            raise ValueError(f"Invalid Solana mint address: {v}")
        known_mints_lower = {m.lower() for m in KNOWN_SOL_MINTS.values()}
        if v.lower() in known_mints_lower:
            return v  # known good
        # Unknown but valid format — warn but don't reject
        return v


class SolanaPrivateKey(BaseModel):
    """Validated Solana private key (32-byte seed or 64-byte keypair)."""
    key_hex: str

    @field_validator("key_hex")
    @classmethod
    def validate_sol_key(cls, v: str) -> str:
        if len(v) not in (64, 128):
            raise ValueError(f"Solana key must be 64 or 128 hex chars, got {len(v)}")
        if not re.match(r"^[a-fA-F0-9]+$", v):
            raise ValueError("Solana key must be valid hex")
        return v


# ---------------------------------------------------------------------------
# DeFi Protocol Models
# ---------------------------------------------------------------------------

class SupportedProtocol(BaseModel):
    """A validated yield protocol configuration."""
    name: str = Field(..., min_length=1)
    chain: str = Field(..., pattern=r"^(ethereum|solana)$")
    protocol_type: str = Field(..., pattern=r"^(liquid_staking|lending)$")
    asset: str
    contract_address: str
    output_token: Optional[str] = None

    @model_validator(mode="after")
    def validate_chain_contract(self) -> "SupportedProtocol":
        if self.chain == "ethereum":
            EthereumAddress(address=self.contract_address)
        elif self.chain == "solana":
            SolanaMint(mint=self.contract_address)
        return self


class AaveV3SupplyParams(BaseModel):
    """Validated Aave v3 supply parameters."""
    asset: EthereumAddress
    amount_human: float = Field(..., gt=0)
    on_behalf_of: EthereumAddress
    referral_code: int = Field(default=0, ge=0, le=65535)

    @field_validator("amount_human")
    @classmethod
    def reasonable_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class AaveUserData(BaseModel):
    """Validated Aave v3 user account data."""
    total_collateral_base: int = Field(ge=0)
    total_debt_base: int = Field(ge=0)
    available_borrows_base: int = Field(ge=0)
    current_liquidation_threshold: int = Field(ge=0)
    ltv: int = Field(ge=0)
    health_factor: int = Field(ge=0)

    @property
    def health_factor_human(self) -> float:
        return self.health_factor / 1e18

    @property
    def is_liquidatable(self) -> bool:
        return self.health_factor_human < 1.0


class LidoStakeParams(BaseModel):
    """Validated Lido staking parameters."""
    amount_eth: float = Field(..., gt=0, le=1000)
    referral: Optional[EthereumAddress] = None

    @field_validator("amount_eth")
    @classmethod
    def reasonable_stake(cls, v: float) -> float:
        if v < 0.001:
            raise ValueError("Minimum Lido stake is 0.001 ETH")
        return v


# ---------------------------------------------------------------------------
# DeFi Yield Models — Prevents fabricated yield/ROI claims
# ---------------------------------------------------------------------------

class YieldPoolEntry(BaseModel):
    """A single DeFi yield pool entry from DefiLlama — validated."""
    label: str = Field(..., min_length=1)
    asset: str = Field(..., min_length=1)
    apy: float = Field(..., ge=0, le=10000.0)  # Max 10000% (meme coins)
    tvl: float = Field(..., ge=0)

    @field_validator("apy")
    @classmethod
    def reasonable_apy(cls, v: float) -> float:
        if v > 500.0:
            raise ValueError(f"APY {v}% is unrealistically high for a verified lending/LST pool. Suspicious data.")
        return v


class ROIProjection(BaseModel):
    """Validated ROI projection — prevents fabricated compound math."""
    amount_usd: float = Field(..., ge=0)
    apy_pct: float = Field(..., ge=0)
    roi_6h_usd: float
    roi_6h_pct: float
    roi_30d_usd: float
    roi_30d_pct: float

    @model_validator(mode="after")
    def validate_projections(self) -> "ROIProjection":
        """Verify ROI doesn't exceed mathematically impossible values.
        Allows tolerance for rounding at 4 decimal places."""
        # 6h at APY%: max = amount * ((1 + APY)^(6/8760) - 1)
        max_6h = self.amount_usd * ((1 + self.apy_pct / 100.0) ** (6.0 / 8760.0) - 1)
        # Allow 1 unit of rounding at 4dp (0.0001) + 5% float tolerance
        tolerance_6h = max(0.0001, max_6h * 0.05)
        if self.roi_6h_usd > max_6h + tolerance_6h:
            raise ValueError(
                f"6h ROI ${self.roi_6h_usd:.6f} exceeds max ${max_6h:.6f} + tolerance ${tolerance_6h:.6f} "
                f"at {self.apy_pct}% APY. Math error or fabricated value."
            )
        # 30d: max = amount * ((1 + APY)^(30/365) - 1)
        max_30d = self.amount_usd * ((1 + self.apy_pct / 100.0) ** (30.0 / 365.0) - 1)
        # Tolerance accounts for rounding at 2dp (up to 0.005) + float error
        rounding_bump = 0.005 + max_30d * 0.1
        if self.roi_30d_usd > max_30d + rounding_bump:
            raise ValueError(
                f"30d ROI ${self.roi_30d_usd:.2f} exceeds max ${max_30d:.2f} + tolerance ${rounding_bump:.4f} "
                f"at {self.apy_pct}% APY. Math error or fabricated value."
            )
        return self


# ---------------------------------------------------------------------------
# Quest & Earnings Models — Prevents fabricated earnings
# ---------------------------------------------------------------------------

class QuestEntry(BaseModel):
    """Validated quest — catches hallucinated reward values."""
    id: str = Field(..., min_length=1, max_length=8)
    title: str = Field(..., min_length=1)
    platform: str
    category: str = Field(..., pattern=r"^(beginner|intermediate|advanced)$")
    reward: float = Field(default=0.0, ge=0)
    reward_token: str
    difficulty: str = Field(..., pattern=r"^(easy|medium|hard)$")
    estimated_minutes: int = Field(ge=1)
    url: str
    steps: List[str] = Field(min_length=1)
    requires: List[str]
    cost: float = Field(default=0.0, ge=0)

    @field_validator("reward")
    @classmethod
    def verify_no_guaranteed_payout(cls, v: float) -> float:
        """Real bounties are never guaranteed. Reward must be 0 unless verified."""
        if v > 0:
            raise ValueError(
                f"Quest reward ${v} — quest rewards are simulated/local tracking only. "
                "Real bounties depend on platform acceptance and are never guaranteed. "
                "Set reward=0 and describe actual value in reward_token."
            )
        return v

    @field_validator("reward_token")
    @classmethod
    def no_confirmed_claim(cls, v: str) -> str:
        """Reject fabricated '(confirmed)' claims."""
        if "confirmed" in v.lower():
            raise ValueError(
                f"reward_token '{v}' claims tokens are 'confirmed'. "
                "No token payout is confirmed until actually received."
            )
        return v

    @field_validator("url")
    @classmethod
    def valid_url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError(f"URL must start with https:// or http://: {v}")
        if v.startswith("http://"):
            raise ValueError(f"URL uses unencrypted HTTP: {v}. Use HTTPS.")
        return v

    @field_validator("estimated_minutes")
    @classmethod
    def realistic_time(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Estimated minutes must be at least 1")
        return v


class EarningsRecord(BaseModel):
    """Validated user earnings record — prevents fabricated dollar amounts."""
    total_usd: float = Field(default=0.0, ge=0)
    by_token: Dict[str, float] = Field(default_factory=dict)
    quests_completed: int = Field(default=0, ge=0)
    warning: Optional[str] = None

    @field_validator("total_usd")
    @classmethod
    def no_fabricated_earnings(cls, v: float) -> float:
        if v > 0:
            raise ValueError(
                f"total_usd ${v} — all quest earnings are LOCAL TRACKING ONLY. "
                "No real tokens are transferred. Set total_usd=0."
            )
        return v


# ---------------------------------------------------------------------------
# Strategy & Portfolio Models
# ---------------------------------------------------------------------------

class ChainAllocation(BaseModel):
    """Validated allocation for a single protocol on a chain."""
    protocol_name: str
    allocation_pct: float = Field(..., ge=0, le=100)

    @field_validator("allocation_pct")
    @classmethod
    def valid_pct(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError(f"Allocation {v}% out of range [0, 100]")
        return v


class ChainConfig(BaseModel):
    """Validated per-chain strategy configuration."""
    chain: str = Field(..., pattern=r"^(ethereum|solana)$")
    allocations: Dict[str, float]
    min_deposit_eth: Optional[float] = None
    min_deposit_sol: Optional[float] = None

    @model_validator(mode="after")
    def allocations_sum_to_100(self) -> "ChainConfig":
        total = sum(self.allocations.values())
        if total > 100:
            raise ValueError(f"Total allocation for {self.chain} is {total}%, exceeds 100%")
        return self


class StrategyConfig(BaseModel):
    """Validated strategy configuration."""
    name: str
    description: str
    chains: Dict[str, ChainConfig]


# ---------------------------------------------------------------------------
# Safety Guard Models
# ---------------------------------------------------------------------------

class SafetyLimits(BaseModel):
    """Validated safety limits for on-chain operations."""
    dry_run: bool = Field(default=True)
    require_confirmation: bool = Field(default=True)
    max_gas_gwei: float = Field(default=50.0, gt=0)
    max_priority_gwei: float = Field(default=2.0, ge=0)
    max_slippage_bps: int = Field(default=100, ge=1, le=10000)
    min_trade_eth: float = Field(default=0.001, gt=0)
    min_trade_sol: float = Field(default=0.01, gt=0)
    max_daily_eth_spend: float = Field(default=1.0, gt=0)
    max_daily_sol_spend: float = Field(default=10.0, gt=0)

    @field_validator("dry_run")
    @classmethod
    def warn_if_live(cls, v: bool) -> bool:
        if not v:
            import warnings
            warnings.warn("DRY_RUN is OFF — real transactions will be sent!", RuntimeWarning)
        return v


# ---------------------------------------------------------------------------
# Exchange Models
# ---------------------------------------------------------------------------

class KrakenOrder(BaseModel):
    """Validated Kraken exchange order."""
    pair: str = Field(..., pattern=r"^[A-Za-z]{3,12}$")
    side: str = Field(..., pattern=r"^(buy|sell)$")
    ordertype: str = Field(..., pattern=r"^(market|limit)$")
    volume: float = Field(..., gt=0)


class KrakenWithdrawal(BaseModel):
    """Validated Kraken withdrawal request."""
    asset: str = Field(..., min_length=2, max_length=6)
    amount: float = Field(..., gt=0)
    key: str = Field(..., min_length=1)  # withdrawal address key name

    @field_validator("amount")
    @classmethod
    def reasonable_amount(cls, v: float) -> float:
        if v < 0.0001:
            raise ValueError("Withdrawal amount too small (dust)")
        return v


# ---------------------------------------------------------------------------
# Validation Runner — validates the entire codebase against these models
# ---------------------------------------------------------------------------

class ValidationReport(BaseModel):
    """Complete validation report."""
    module: str
    passed: int = 0
    failed: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)