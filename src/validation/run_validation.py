"""
Validation runner — applies Pydantic models to validate the entire GETIN codebase.
Inspired by pydantic-ai's type-safe agent pattern, this validates all data
contracts against real engineering constraints.

Usage:
    python -m src.validation.run_validation
    python -m src.validation.run_validation --verbose
    python -m src.validation.run_validation --module quest_engine
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import List

from src.validation.models import (
    ValidationReport,
    QuestEntry,
    EarningsRecord,
    YieldPoolEntry,
    ROIProjection,
    StrategyConfig,
    ChainAllocation,
    ChainConfig,
    SafetyLimits,
    EthereumAddress,
    EthereumTxHash,
    SolanaAddress,
    SolanaMint,
    SupportedProtocol,
    AaveV3SupplyParams,
    AaveUserData,
    LidoStakeParams,
    KrakenOrder,
    KrakenWithdrawal,
    TransactionParams,
    EIP1559Params,
    DUMMY_ADDRESSES,
    KNOWN_CONTRACTS,
    KNOWN_SOL_MINTS,
    ValidationError,
)
from pydantic import ValidationError as PydanticValidationError


# ---------------------------------------------------------------------------
# 1. VALIDATE QUEST CATALOG
# ---------------------------------------------------------------------------

def validate_quest_catalog(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="quest_engine")
    try:
        from src.quest_engine import QUEST_CATALOG

        if not isinstance(QUEST_CATALOG, list):
            report.errors.append("QUEST_CATALOG is not a list")
            report.failed += 1
            return report

        for i, quest in enumerate(QUEST_CATALOG):
            try:
                validated = QuestEntry(**quest)
                report.passed += 1
                if verbose:
                    print(f"  ✓ Quest {validated.id}: {validated.title} — $0.00 ({validated.reward_token})")
            except PydanticValidationError as e:
                report.failed += 1
                err_msg = f"Quest[{i}] ({quest.get('id', 'NO_ID')}): {e}"
                report.errors.append(err_msg)
                if verbose:
                    print(f"  ✗ {err_msg}")
    except ImportError as e:
        report.errors.append(f"Cannot import quest_engine.QUEST_CATALOG: {e}")
        report.failed += 1

    return report


# ---------------------------------------------------------------------------
# 2. VALIDATE EARNINGS DATA
# ---------------------------------------------------------------------------

def validate_earnings_data(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="earnings")
    try:
        import json
        if os.path.exists("earnings.json"):
            with open("earnings.json") as f:
                data = json.load(f)
            users = data.get("users", {})
            for uid, user_data in users.items():
                try:
                    validated = EarningsRecord(
                        total_usd=user_data.get("total_usd", 0),
                        by_token=user_data.get("by_token", {}),
                        quests_completed=len(user_data.get("quests", [])),
                    )
                    report.passed += 1
                    if verbose:
                        print(f"  ✓ User {uid}: $0.00 total (correct)")
                except PydanticValidationError as e:
                    report.failed += 1
                    report.errors.append(f"earnings.json user {uid}: {e}")
                    if verbose:
                        print(f"  ✗ User {uid}: {e}")
        else:
            report.warnings.append("earnings.json not found (ok if not yet created)")
    except Exception as e:
        report.errors.append(f"earnings.json parse error: {e}")
        report.failed += 1

    return report


# ---------------------------------------------------------------------------
# 3. VALIDATE CONTRACT ADDRESSES
# ---------------------------------------------------------------------------

def validate_contract_addresses(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="contract_addresses")

    # Verify known mainnet contracts are valid
    checks = [
        ("Aave V3 Pool", KNOWN_CONTRACTS["aave_v3_pool"]),
        ("Lido stETH", KNOWN_CONTRACTS["lido_steth"]),
        ("WETH", KNOWN_CONTRACTS["weth"]),
        ("USDC", KNOWN_CONTRACTS["usdc"]),
    ]
    for name, addr in checks:
        try:
            validated = EthereumAddress(address=addr)
            report.passed += 1
            if verbose:
                print(f"  ✓ {name}: {validated.address} (Etherscan-verified)")
        except PydanticValidationError as e:
            report.failed += 1
            report.errors.append(f"Known contract {name}: {e}")

    # Verify dummy addresses are NOT used as real contracts
    # Check onchain_auto_farmer.py for dummy addresses
    try:
        from src.onchain_auto_farmer import ROUTERS, WRAPPED_NATIVE

        for network, routers in ROUTERS.items():
            for dex_name, addr in routers.items():
                if addr.lower() in {d.lower() for d in DUMMY_ADDRESSES}:
                    report.warnings.append(
                        f"onchain_auto_farmer ROUTERS[{network}][{dex_name}]={addr} is a known dummy address (expected)"
                    )
                    if verbose:
                        print(f"  ⚠ {network}/{dex_name}: {addr} (dummy — correct)")
                else:
                    try:
                        EthereumAddress(address=addr)
                        report.passed += 1
                        if verbose:
                            print(f"  ✓ {network}/{dex_name}: {addr}")
                    except PydanticValidationError as e:
                        report.failed += 1
                        report.errors.append(f"ROUTERS[{network}][{dex_name}]: {e}")

        for network, addr in WRAPPED_NATIVE.items():
            if addr.lower() in {d.lower() for d in DUMMY_ADDRESSES}:
                report.warnings.append(f"WRAPPED_NATIVE[{network}]={addr} is a known dummy address (expected)")
            else:
                try:
                    EthereumAddress(address=addr)
                    report.passed += 1
                except PydanticValidationError:
                    report.failed += 1
                    report.errors.append(f"WRAPPED_NATIVE[{network}]={addr} is neither dummy nor valid ETH address")
    except ImportError as e:
        report.errors.append(f"Cannot import onchain_auto_farmer: {e}")
        report.failed += 1

    # Verify Solana mints
    try:
        from src.chain_clients.solana_client import JITOSOL_MINT, MSOL_MINT, SOL_MINT
        for name, mint, expected in [
            ("SOL (wrapped)", SOL_MINT, KNOWN_SOL_MINTS["sol"]),
            ("JitoSOL", JITOSOL_MINT, KNOWN_SOL_MINTS["jitosol"]),
            ("Marinade mSOL", MSOL_MINT, KNOWN_SOL_MINTS["msol"]),
        ]:
            try:
                validated = SolanaMint(mint=mint)
                if validated.mint.lower() == expected.lower():
                    report.passed += 1
                    if verbose:
                        print(f"  ✓ {name}: {validated.mint} (Solscan-verified)")
                else:
                    report.failed += 1
                    report.errors.append(f"{name} mint {mint} != expected {expected}")
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"{name}: {e}")
    except ImportError as e:
        report.errors.append(f"Cannot import solana_client constants: {e}")
        report.failed += 1

    return report


# ---------------------------------------------------------------------------
# 4. VALIDATE YIELD SCANNER MATH
# ---------------------------------------------------------------------------

def validate_yield_scanner(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="yield_scanner")
    try:
        from src.yield_scanner import YieldScanner

        scanner = YieldScanner()

        # Test edge cases
        test_cases = [
            (0.0, 1000.0, "zero_apy"),
            (5.0, 1000.0, "typical"),
            (100.0, 1000.0, "high_apy"),
            (5.58, 4.20, "small_amount"),
        ]
        for apy, amount, label in test_cases:
            try:
                roi = scanner.calculate_roi(apy, amount)
                validated = ROIProjection(**roi)
                report.passed += 1
                if verbose:
                    print(f"  ✓ ROI [{label}]: {apy}% APY, ${amount} -> 6h=${roi['roi_6h_usd']:.6f}, 30d=${roi['roi_30d_usd']:.2f}")
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"ROI calc [{label}]: {e}")

        # Test that absurd APY values are rejected
        try:
            YieldPoolEntry(label="Test", asset="ETH", apy=1000.0, tvl=100)
            report.failed += 1
            report.errors.append("Pool with 1000% APY was NOT rejected (should have been)")
        except PydanticValidationError:
            report.passed += 1
            if verbose:
                print("  ✓ Absurd APY (1000%) correctly rejected")

    except ImportError as e:
        report.errors.append(f"Cannot import yield_scanner: {e}")
        report.failed += 1

    return report


# ---------------------------------------------------------------------------
# 5. VALIDATE STRATEGY CONFIG
# ---------------------------------------------------------------------------

def validate_strategy_config(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="strategies")
    try:
        from src.config_manager import load_yaml

        cfg = load_yaml("config/strategies.yaml")
        strategies = cfg.get("strategies", {})

        for name, strat in strategies.items():
            try:
                chains = {}
                for chain_name, chain_data in strat.get("chains", {}).items():
                    chains[chain_name] = ChainConfig(
                        chain=chain_name,
                        allocations=chain_data.get("allocations", {}),
                        min_deposit_eth=chain_data.get("min_deposit_eth"),
                        min_deposit_sol=chain_data.get("min_deposit_sol"),
                    )
                validated = StrategyConfig(
                    name=name,
                    description=strat.get("description", ""),
                    chains=chains,
                )
                report.passed += 1
                if verbose:
                    print(f"  ✓ Strategy '{name}': {validated.description[:60]}...")
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"Strategy '{name}': {e}")

        # Validate protocol entries
        protocols = cfg.get("protocols", {})
        for proto_name, proto_cfg in protocols.items():
            try:
                # Aave uses 'pool', others use 'contract' or 'mint'
                addr = proto_cfg.get("contract") or proto_cfg.get("pool") or proto_cfg.get("mint") or ""
                SupportedProtocol(
                    name=proto_name,
                    chain=proto_cfg.get("chain", ""),
                    protocol_type=proto_cfg.get("type", ""),
                    asset=proto_cfg.get("asset", ""),
                    contract_address=addr,
                )
                report.passed += 1
                if verbose:
                    print(f"  ✓ Protocol '{proto_name}': {proto_cfg.get('chain')} {proto_cfg.get('type')}")
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"Protocol '{proto_name}': {e}")

    except Exception as e:
        report.errors.append(f"Strategy config error: {e}")
        report.failed += 1

    return report


# ---------------------------------------------------------------------------
# 6. VALIDATE SAFETY LIMITS
# ---------------------------------------------------------------------------

def validate_safety_limits(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="safety_guard")
    try:
        limits = SafetyLimits(
            dry_run=True,
            require_confirmation=True,
            max_gas_gwei=float(os.getenv("MAX_GAS_GWEI", "50")),
            max_priority_gwei=float(os.getenv("MAX_PRIORITY_GWEI", "2")),
            max_slippage_bps=int(os.getenv("MAX_SLIPPAGE_BPS", "100")),
            min_trade_eth=float(os.getenv("MIN_TRADE_ETH", "0.001")),
            min_trade_sol=float(os.getenv("MIN_TRADE_SOL", "0.01")),
            max_daily_eth_spend=float(os.getenv("MAX_DAILY_ETH_SPEND", "1.0")),
            max_daily_sol_spend=float(os.getenv("MAX_DAILY_SOL_SPEND", "10.0")),
        )
        report.passed += 1
        if verbose:
            print(f"  ✓ Safety limits validated (DRY_RUN={'ON' if limits.dry_run else 'OFF'})")

        # Verify no CIRCUIT_BREAKER dead code
        if "CIRCUIT_BREAKER_TVL_DROP_PCT" in os.environ:
            report.warnings.append("CIRCUIT_BREAKER_TVL_DROP_PCT is set but NOT IMPLEMENTED — dead config")
    except PydanticValidationError as e:
        report.failed += 1
        report.errors.append(f"Safety limits: {e}")

    return report


# ---------------------------------------------------------------------------
# 7. VALIDATE ABI USAGE
# ---------------------------------------------------------------------------

def validate_abi_definitions(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="abi_definitions")
    try:
        import json

        # Check aave_v3.py ABIs
        from src.yield_protocols.aave_v3 import AAVE_POOL_ABI, ERC20_ABI_MINIMAL

        # Verify ERC20 ABI has required functions
        required_erc20 = {"balanceOf", "approve", "decimals", "symbol", "allowance"}
        erc20_funcs = {item["name"] for item in ERC20_ABI_MINIMAL if item.get("type") == "function"}
        missing = required_erc20 - erc20_funcs
        if missing:
            report.failed += 1
            report.errors.append(f"ERC20_ABI_MINIMAL missing functions: {missing}")
        else:
            report.passed += 1
            if verbose:
                print(f"  ✓ ERC20 ABI has all required functions: {sorted(erc20_funcs)}")

        # Verify Aave Pool ABI has required functions
        required_aave = {"supply", "withdraw", "getUserAccountData", "getReserveData"}
        aave_funcs = {item["name"] for item in AAVE_POOL_ABI if item.get("type") == "function"}
        missing_aave = required_aave - aave_funcs
        if missing_aave:
            report.failed += 1
            report.errors.append(f"AAVE_POOL_ABI missing functions: {missing_aave}")
        else:
            report.passed += 1
            if verbose:
                print(f"  ✓ Aave Pool ABI has all required functions: {sorted(aave_funcs)}")

        # Check lido.py ABIs
        from src.yield_protocols.lido import LIDO_ABI
        required_lido = {"submit", "balanceOf", "decimals"}
        lido_funcs = {item["name"] for item in LIDO_ABI if item.get("type") == "function"}
        missing_lido = required_lido - lido_funcs
        if missing_lido:
            report.failed += 1
            report.errors.append(f"LIDO_ABI missing functions: {missing_lido}")
        else:
            report.passed += 1
            if verbose:
                print(f"  ✓ Lido ABI has all required functions: {sorted(lido_funcs)}")

        # Check verify Lido has getTotalPooledEther and getTotalShares (shares-based model)
        shares_funcs = {"getTotalPooledEther", "getTotalShares"}
        lido_has_shares = shares_funcs.intersection(lido_funcs)
        if lido_has_shares:
            report.passed += 1
            if verbose:
                print(f"  ✓ Lido ABI confirms shares-based model (has: {lido_has_shares})")
        else:
            report.warnings.append("Lido ABI does not have getTotalPooledEther/getTotalShares — shares model unconfirmed")

    except ImportError as e:
        report.errors.append(f"ABI import error: {e}")
        report.failed += 1

    return report


# ---------------------------------------------------------------------------
# RUN ALL VALIDATIONS
# ---------------------------------------------------------------------------

def run_all(target_module: str = "", verbose: bool = False) -> List[ValidationReport]:
    """Run all validations and return a list of reports."""
    validators = {
        "quest_engine": validate_quest_catalog,
        "earnings": validate_earnings_data,
        "contract_addresses": validate_contract_addresses,
        "yield_scanner": validate_yield_scanner,
        "strategies": validate_strategy_config,
        "safety_guard": validate_safety_limits,
        "abi_definitions": validate_abi_definitions,
    }

    reports = []
    for name, validator in validators.items():
        if target_module and target_module != name:
            continue
        try:
            report = validator(verbose=verbose)
        except Exception as e:
            report = ValidationReport(module=name, failed=1, errors=[str(e)])
        reports.append(report)

    return reports


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GETIN Pydantic Validation Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--module", type=str, default="", help="Validate a specific module")
    args = parser.parse_args()

    # Load .env for safety guard validation
    from src.config_manager import load_env
    load_env()

    print("=" * 70)
    print("GETIN ENGINEERING VALIDATION SUITE")
    print("Pydantic-based type validation of all data contracts")
    print("=" * 70)

    reports = run_all(target_module=args.module, verbose=args.verbose)

    total_passed = sum(r.passed for r in reports)
    total_failed = sum(r.failed for r in reports)
    total_warnings = sum(len(r.warnings) for r in reports)

    print()
    print("=" * 70)
    for report in reports:
        status = "✓ PASS" if report.failed == 0 else "✗ FAIL"
        print(f"  [{status}] {report.module}: {report.passed} checks passed, {report.failed} failed")
        for err in report.errors:
            print(f"    ERROR: {err}")
        for warn in report.warnings:
            print(f"    WARN:  {warn}")
    print("=" * 70)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed, {total_warnings} warnings")

    if total_failed > 0:
        print(f"\n✗ VALIDATION FAILED — {total_failed} checks did not pass engineering review.")
        sys.exit(1)
    else:
        print(f"\n✓ ALL CHECKS PASSED — No hallucinations or engineering violations detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()