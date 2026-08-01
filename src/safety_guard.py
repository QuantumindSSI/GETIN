import os
from typing import Any, Dict


class SafetyGuard:
    """
    Safety limits for all on-chain operations.
    Enforces static caps on gas, slippage, and position size.
    NOTE: TVL-based anomaly detection (circuit breaker) requires
    external monitoring — not implemented here.
    """

    DEFAULTS = {
        "MAX_GAS_GWEI": "50",
        "MAX_PRIORITY_GWEI": "2",
        "MAX_SLIPPAGE_BPS": "100",
        "MIN_TRADE_ETH": "0.001",
        "MIN_TRADE_SOL": "0.01",
        "MAX_DAILY_ETH_SPEND": "1.0",
        "MAX_DAILY_SOL_SPEND": "10.0",
        "DRY_RUN": "true",
        "REQUIRE_CONFIRMATION": "true",
    }

    def __init__(self):
        self._config: Dict[str, Any] = {}
        for key, default in self.DEFAULTS.items():
            raw = os.getenv(key, default)
            if raw.lower() in ("true", "1", "yes"):
                self._config[key] = True
            elif raw.lower() in ("false", "0", "no"):
                self._config[key] = False
            else:
                try:
                    if "." in raw:
                        self._config[key] = float(raw)
                    else:
                        self._config[key] = int(raw)
                except ValueError:
                    self._config[key] = raw

    def get(self, key: str) -> Any:
        return self._config.get(key, self.DEFAULTS.get(key))

    def is_dry_run(self) -> bool:
        return bool(self._config.get("DRY_RUN", True))

    def require_confirmation(self) -> bool:
        return bool(self._config.get("REQUIRE_CONFIRMATION", True))

    def check_gas_price(self, gas_gwei: float) -> bool:
        max_gwei = float(self._config.get("MAX_GAS_GWEI", 50))
        if gas_gwei > max_gwei:
            raise SafetyError(
                f"Gas price {gas_gwei:.2f} gwei exceeds max {max_gwei} gwei. "
                f"Wait for lower gas or raise MAX_GAS_GWEI."
            )
        return True

    def check_slippage(self, slippage_bps: int) -> bool:
        max_bps = int(self._config.get("MAX_SLIPPAGE_BPS", 100))
        if slippage_bps > max_bps:
            raise SafetyError(
                f"Slippage {slippage_bps} bps exceeds max {max_bps} bps."
            )
        return True

    def check_min_trade_eth(self, amount: float) -> bool:
        mini = float(self._config.get("MIN_TRADE_ETH", 0.001))
        if amount < mini:
            raise SafetyError(
                f"Trade size {amount} ETH below minimum {mini} ETH."
            )
        return True

    def check_min_trade_sol(self, amount: float) -> bool:
        mini = float(self._config.get("MIN_TRADE_SOL", 0.01))
        if amount < mini:
            raise SafetyError(
                f"Trade size {amount} SOL below minimum {mini} SOL."
            )
        return True

    def confirm(self, action: str, details: str) -> bool:
        if not self.require_confirmation():
            return True
        print("\n" + "=" * 60)
        print(f"CONFIRMATION REQUIRED: {action}")
        print("=" * 60)
        print(details)
        print("=" * 60)
        if self.is_dry_run():
            print("[DRY RUN] No real transaction will be sent.")
            return True
        resp = input("Type 'yes' to proceed: ").strip().lower()
        return resp == "yes"


class SafetyError(Exception):
    """Raised when a safety rule is violated."""
    pass
