"""Unit tests for GETIN core modules — yield math, validation models, wallet setup."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestYieldScanner:
    def test_compound_roi_zero_apy(self):
        from src.yield_scanner import YieldScanner
        r = YieldScanner().calculate_roi(0.0, 1000.0)
        assert r["roi_6h_usd"] == 0.0
        assert r["roi_30d_usd"] == 0.0

    def test_compound_roi_typical(self):
        from src.yield_scanner import YieldScanner
        r = YieldScanner().calculate_roi(5.0, 1000.0)
        assert 3.90 < r["roi_30d_usd"] < 4.20

    def test_compound_roi_high_apy(self):
        from src.yield_scanner import YieldScanner
        r = YieldScanner().calculate_roi(100.0, 1000.0)
        assert 55 < r["roi_30d_usd"] < 62

    def test_small_amount(self):
        from src.yield_scanner import YieldScanner
        r = YieldScanner().calculate_roi(5.58, 4.20)
        assert r["amount_usd"] == 4.2
        assert r["roi_6h_usd"] >= 0.0


class TestValidationModels:
    def test_ethereum_address_validates(self):
        from src.validation.models import EthereumAddress
        addr = EthereumAddress(address="0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2")
        assert addr.address.startswith("0x")

    def test_ethereum_address_rejects_dummy(self):
        from src.validation.models import EthereumAddress
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EthereumAddress(address="0x000000000000000000000000000000000000DEAD")

    def test_solana_mint_validates_known(self):
        from src.validation.models import SolanaMint
        m = SolanaMint(mint="J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn")
        assert m.mint == "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"

    def test_yield_pool_rejects_absurd_apy(self):
        from src.validation.models import YieldPoolEntry
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            YieldPoolEntry(label="Test", asset="ETH", apy=10000.0, tvl=100)

    def test_safety_limits_default(self):
        from src.validation.models import SafetyLimits
        limits = SafetyLimits()
        assert limits.dry_run is True
        assert limits.max_gas_gwei == 50

    def test_roi_projection_rejects_impossible_math(self):
        from src.validation.models import ROIProjection
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            # 100% APY for 30d should be ~58.63, not 100
            ROIProjection(amount_usd=1000, apy_pct=100, roi_6h_usd=0.47, roi_6h_pct=0.047, roi_30d_usd=100.0, roi_30d_pct=10.0)


class TestLogger:
    def test_log_writes_record(self):
        from src.logger import ActivityLogger
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as f:
            path = f.name
        try:
            logger = ActivityLogger(path)
            logger.log("Monad", "test_action", "0xabc123", {"key": "val"})
            with open(path) as fh:
                lines = fh.readlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["project"] == "Monad"
            assert record["action"] == "test_action"
        finally:
            os.unlink(path)


class TestWalletSetup:
    def test_generate_eth_wallet(self):
        from src.wallet_setup import generate_wallet
        addr = generate_wallet("_pytest_eth")
        assert addr.startswith("0x")
        assert len(addr) == 42

    def test_generate_solana_wallet(self):
        from src.wallet_setup import generate_solana_wallet
        addr = generate_solana_wallet("_pytest_sol")
        assert len(addr) >= 32
        assert len(addr) <= 44

    def test_import_mnemonic(self):
        from src.wallet_setup import import_mnemonic
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        addr = import_mnemonic(mnemonic, "_pytest_import")
        assert addr.startswith("0x")
        assert len(addr) == 42