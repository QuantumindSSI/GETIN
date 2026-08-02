"""Tests for the AI sanitizer module (fallback mode — no API key needed)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _clear_ai_cache():
    """Ensure AI module starts fresh each test — no stale globals."""
    from src import ai_sanitizer
    ai_sanitizer._available = None
    ai_sanitizer._command_agent = None
    ai_sanitizer._yield_agent = None
    ai_sanitizer._tx_agent = None
    ai_sanitizer._portfolio_agent = None
    ai_sanitizer._message_agent = None
    ai_sanitizer._apy_validator = None
    ai_sanitizer._sanitizer = None
    ai_sanitizer._shared_model = None
    ai_sanitizer._cached_token = None
    ai_sanitizer._cached_token_expiry = 0.0
    os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
    # Force fallback mode by unsetting the endpoint
    ai_sanitizer.AZURE_ENDPOINT = ""
    yield
    os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
    # Restore endpoint if it was set before
    ai_sanitizer.AZURE_ENDPOINT = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://admin-3450-resource.cognitiveservices.azure.com/openai/v1",
    )


class TestAISanitizerFallback:
    """All tests run without an API key — exercising fallback paths."""

    def test_singleton(self):
        from src.ai_sanitizer import get_ai_sanitizer
        a1 = get_ai_sanitizer()
        a2 = get_ai_sanitizer()
        assert a1 is a2

    def test_ai_not_available_when_key_missing(self):
        import subprocess
        from src.ai_sanitizer import _is_ai_available
        # If az CLI is installed and logged in, AI IS available.
        # Skip this assertion if az is present.
        try:
            subprocess.run(["az", "account", "show"], capture_output=True, timeout=5, check=True)
            have_az = True
        except Exception:
            have_az = False
        if have_az:
            pytest.skip("Azure CLI is available — AI validation is expected to work")
        assert _is_ai_available() is False

    def test_sanitise_command_fallback(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_command("invest", {"strategy": "conservative", "budget_gbp": 100})
        assert result.command == "invest"
        assert result.rejected is False

    def test_sanitise_transaction_fallback(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_transaction(
            action="supply",
            protocol="aave_v3",
            chain="ethereum",
            amount=1.0,
            contract_address="0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        )
        assert result.is_safe is True
        assert result.action == "supply"

    def test_sanitise_yield_entry_fallback(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_yield_entry({
            "label": "Aave v3 ETH",
            "asset": "WETH",
            "apy": 3.5,
            "tvl": 1000000,
        })
        assert result.is_plausible is True
        assert result.apy == 3.5

    def test_sanitise_yield_entry_suspicious_apy(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_yield_entry({
            "label": "Suspicious Farm",
            "asset": "SCAM",
            "apy": 600,
            "tvl": 100,
        })
        assert result.is_plausible is False
        assert "500%" in (result.warning or "")

    def test_sanitise_yield_entry_negative_apy(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_yield_entry({
            "label": "Broken Pool",
            "asset": "ETH",
            "apy": -5,
            "tvl": 100,
        })
        assert result.is_plausible is False
        assert "negative" in (result.warning or "").lower()

    def test_sanitise_yield_entry_absurd_apy(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_yield_entry({
            "label": "Meme Farm",
            "asset": "MOON",
            "apy": 99999,
            "tvl": 10,
        })
        assert result.is_plausible is False
        assert "10,000%" in (result.warning or "")

    def test_sanitise_portfolio_action_fallback(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_portfolio_action(
            strategy="conservative",
            budget_gbp=100,
            action_type="invest",
            eth_pct=50,
            sol_pct=50,
        )
        assert result.is_safe is True
        assert result.strategy == "conservative"

    def test_sanitise_message_fallback(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_message("/invest conservative 100")
        assert result.text == "/invest conservative 100"
        assert result.is_safe is True

    def test_safety_report_initial(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        report = ai.get_report()
        assert report.total_checks == 0
        assert report.passed == 0
        assert report.rejected == 0

    def test_sanitise_apy_plausibility_fallback(self):
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        result = ai.sanitise_apy_plausibility("Lido stETH", "ETH", 3.0)
        assert result.is_plausible is True

    def test_all_structured_models_construct(self):
        from src.ai_sanitizer import (
            SanitisedCommand,
            SanitisedTransaction,
            SanitisedYieldData,
            SanitisedPortfolioAction,
            SanitisedMessage,
            SafetyReport,
        )
        SanitisedCommand(command="test", args={})
        SanitisedTransaction(action="test", protocol="t", chain="ethereum")
        SanitisedYieldData(label="l", asset="a", apy=5, tvl=100)
        SanitisedPortfolioAction(strategy="conservative", action_type="invest")
        SanitisedMessage(text="hello", intent="help")
        SafetyReport()