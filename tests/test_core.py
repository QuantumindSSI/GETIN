"""
Unit tests for GETIN core modules.
Validates yield math, quest contracts, safety limits, and wallet setup.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────
# Yield Scanner Tests
# ──────────────────────────────────────────────

class TestYieldScanner:
    def test_compound_roi_zero_apy(self):
        from src.yield_scanner import YieldScanner
        s = YieldScanner()
        r = s.calculate_roi(0.0, 1000.0)
        assert r["roi_6h_usd"] == 0.0
        assert r["roi_30d_usd"] == 0.0

    def test_compound_roi_typical(self):
        from src.yield_scanner import YieldScanner
        s = YieldScanner()
        r = s.calculate_roi(5.0, 1000.0)
        assert 3.90 < r["roi_30d_usd"] < 4.20

    def test_compound_roi_high_apy(self):
        from src.yield_scanner import YieldScanner
        s = YieldScanner()
        r = s.calculate_roi(100.0, 1000.0)
        assert 55 < r["roi_30d_usd"] < 62

    def test_small_amount(self):
        from src.yield_scanner import YieldScanner
        s = YieldScanner()
        r = s.calculate_roi(5.58, 4.20)
        assert r["amount_usd"] == 4.2
        assert r["roi_6h_usd"] >= 0.0


# ──────────────────────────────────────────────
# Quest Engine Tests
# ──────────────────────────────────────────────

class TestQuestEngine:
    def test_all_rewards_zero(self):
        from src.quest_engine import QUEST_CATALOG
        for q in QUEST_CATALOG:
            assert q["reward"] == 0.0, f"Quest {q['id']} has non-zero reward ${q['reward']}"

    def test_no_confirmed_claims(self):
        from src.quest_engine import QUEST_CATALOG
        for q in QUEST_CATALOG:
            assert "confirmed" not in q["reward_token"].lower(), \
                f"Quest {q['id']} claims 'confirmed' in reward_token"

    def test_all_urls_https(self):
        from src.quest_engine import QUEST_CATALOG
        for q in QUEST_CATALOG:
            assert q["url"].startswith("https://"), \
                f"Quest {q['id']} URL is not HTTPS: {q['url']}"

    def test_complete_quest_returns_zero(self):
        from src.quest_engine import QuestTracker
        t = QuestTracker(99999)
        r = t.complete_quest("S1")
        assert r["ok"] is True
        assert r["reward"] == 0.0
        assert r["total_earned"] == 0.0

    def test_earnings_always_zero(self):
        from src.quest_engine import QuestTracker
        t = QuestTracker(99998)
        t.complete_quest("S1")
        t.complete_quest("L1")
        e = t.get_earnings()
        assert e["total_usd"] == 0.0


# ──────────────────────────────────────────────
# Subscription Tests
# ──────────────────────────────────────────────

class TestSubscriptions:
    def test_register_and_tier(self):
        from src.subscriptions import register_user, get_tier
        register_user(55555, "testuser")
        assert get_tier(55555) == "free"

    def test_premium_price_default(self):
        from src.subscriptions import get_premium_price
        assert get_premium_price() > 0

    def test_usage_counter_increments(self):
        from src.subscriptions import register_user, get_usage_count, increment_counter
        register_user(55556, "testuser2")
        assert get_usage_count(55556) == 0
        increment_counter(55556)
        assert get_usage_count(55556) == 1


# ──────────────────────────────────────────────
# Validation Model Tests
# ──────────────────────────────────────────────

class TestValidationModels:
    def test_quest_entry_rejects_nonzero_reward(self):
        from src.validation.models import QuestEntry
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QuestEntry(
                id="X1", title="Test", platform="Test", category="beginner",
                reward=50.0, reward_token="USDC", difficulty="easy",
                estimated_minutes=5, url="https://test.com",
                steps=["Step 1"], requires=[], cost=0,
            )

    def test_quest_entry_rejects_confirmed_claim(self):
        from src.validation.models import QuestEntry
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QuestEntry(
                id="X1", title="Test", platform="Test", category="beginner",
                reward=0.0, reward_token="USDC (confirmed)", difficulty="easy",
                estimated_minutes=5, url="https://test.com",
                steps=["Step 1"], requires=[], cost=0,
            )

    def test_quest_entry_rejects_http_url(self):
        from src.validation.models import QuestEntry
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            QuestEntry(
                id="X1", title="Test", platform="Test", category="beginner",
                reward=0.0, reward_token="USDC", difficulty="easy",
                estimated_minutes=5, url="http://test.com",
                steps=["Step 1"], requires=[], cost=0,
            )

    def test_earnings_record_rejects_nonzero_total(self):
        from src.validation.models import EarningsRecord
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EarningsRecord(total_usd=100.0)

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


# ──────────────────────────────────────────────
# Logger Tests
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Wallet Setup Tests
# ──────────────────────────────────────────────

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