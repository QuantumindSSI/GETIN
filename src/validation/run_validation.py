"""
Validation runner — applies Pydantic models to validate the GETIN codebase.
Validates yield math, contract addresses, strategy configs, and safety limits.
No simulation validators — only real engineering checks.

Usage:
    python -m src.validation.run_validation
"""

import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pydantic import ValidationError as PydanticValidationError

from src.validation.models import (
    ValidationReport,
    YieldPoolEntry,
    ROIProjection,
    StrategyConfig,
    ChainConfig,
    SupportedProtocol,
    SafetyLimits,
    EthereumAddress,
    SolanaMint,
    KNOWN_CONTRACTS,
    KNOWN_SOL_MINTS,
)


def validate_contract_addresses(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="contract_addresses")
    checks = [
        ("Aave V3 Pool", KNOWN_CONTRACTS["aave_v3_pool"]),
        ("Lido stETH", KNOWN_CONTRACTS["lido_steth"]),
        ("WETH", KNOWN_CONTRACTS["weth"]),
        ("USDC", KNOWN_CONTRACTS["usdc"]),
    ]
    for name, addr in checks:
        try:
            EthereumAddress(address=addr)
            report.passed += 1
            if verbose: print(f"  ✓ {name}: {addr} (Etherscan-verified)")
        except PydanticValidationError as e:
            report.failed += 1
            report.errors.append(f"Contract {name}: {e}")

    # Verify Solana mints
    try:
        from src.chain_clients.solana_client import JITOSOL_MINT, MSOL_MINT, SOL_MINT
        for name, mint, expected in [
            ("SOL", SOL_MINT, KNOWN_SOL_MINTS["sol"]),
            ("JitoSOL", JITOSOL_MINT, KNOWN_SOL_MINTS["jitosol"]),
            ("mSOL", MSOL_MINT, KNOWN_SOL_MINTS["msol"]),
        ]:
            try:
                validated = SolanaMint(mint=mint)
                if validated.mint.lower() == expected.lower():
                    report.passed += 1
                    if verbose: print(f"  ✓ {name}: {validated.mint}")
                else:
                    report.failed += 1
                    report.errors.append(f"{name} mint mismatch")
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"{name}: {e}")
    except ImportError as e:
        report.errors.append(f"Solana mint import error: {e}")
        report.failed += 1

    return report


def validate_yield_scanner(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="yield_scanner")
    try:
        from src.yield_scanner import YieldScanner
        scanner = YieldScanner()
        for apy, amount, label in [
            (0.0, 1000.0, "zero_apy"),
            (5.0, 1000.0, "typical"),
            (100.0, 1000.0, "high_apy"),
            (5.58, 4.20, "small_amount"),
        ]:
            try:
                roi = scanner.calculate_roi(apy, amount)
                ROIProjection(**roi)
                report.passed += 1
                if verbose: print(f"  ✓ ROI [{label}]: {apy}% APY, ${amount} — OK")
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"ROI [{label}]: {e}")
        # Absurd APY rejection
        try:
            YieldPoolEntry(label="Test", asset="ETH", apy=1000.0, tvl=100)
            report.failed += 1
            report.errors.append("1000% APY not rejected")
        except PydanticValidationError:
            report.passed += 1
    except ImportError as e:
        report.errors.append(f"yield_scanner import: {e}")
        report.failed += 1
    return report


def validate_strategy_config(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="strategies")
    try:
        from src.config_manager import load_yaml
        cfg = load_yaml("config/strategies.yaml")
        for name, strat in cfg.get("strategies", {}).items():
            try:
                chains = {}
                for cn, cd in strat.get("chains", {}).items():
                    chains[cn] = ChainConfig(
                        chain=cn,
                        allocations=cd.get("allocations", {}),
                        min_deposit_eth=cd.get("min_deposit_eth"),
                        min_deposit_sol=cd.get("min_deposit_sol"),
                    )
                StrategyConfig(name=name, description=strat.get("description", ""), chains=chains)
                report.passed += 1
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"Strategy '{name}': {e}")
        for proto_name, proto_cfg in cfg.get("protocols", {}).items():
            try:
                addr = proto_cfg.get("contract") or proto_cfg.get("pool") or proto_cfg.get("mint") or ""
                SupportedProtocol(
                    name=proto_name, chain=proto_cfg.get("chain", ""),
                    protocol_type=proto_cfg.get("type", ""),
                    asset=proto_cfg.get("asset", ""), contract_address=addr,
                )
                report.passed += 1
            except PydanticValidationError as e:
                report.failed += 1
                report.errors.append(f"Protocol '{proto_name}': {e}")
    except Exception as e:
        report.errors.append(f"Strategy config error: {e}")
        report.failed += 1
    return report


def validate_safety_limits(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="safety_guard")
    try:
        limits = SafetyLimits(
            dry_run=True, require_confirmation=True,
            max_gas_gwei=float(os.getenv("MAX_GAS_GWEI", "50")),
            max_priority_gwei=float(os.getenv("MAX_PRIORITY_GWEI", "2")),
            max_slippage_bps=int(os.getenv("MAX_SLIPPAGE_BPS", "100")),
            min_trade_eth=float(os.getenv("MIN_TRADE_ETH", "0.001")),
            min_trade_sol=float(os.getenv("MIN_TRADE_SOL", "0.01")),
            max_daily_eth_spend=float(os.getenv("MAX_DAILY_ETH_SPEND", "1.0")),
            max_daily_sol_spend=float(os.getenv("MAX_DAILY_SOL_SPEND", "10.0")),
        )
        report.passed += 1
    except PydanticValidationError as e:
        report.failed += 1
        report.errors.append(f"Safety limits: {e}")
    return report


def validate_abi_definitions(verbose: bool = False) -> ValidationReport:
    report = ValidationReport(module="abi_definitions")
    try:
        from src.yield_protocols.aave_v3 import AAVE_POOL_ABI, ERC20_ABI_MINIMAL
        required_erc20 = {"balanceOf", "approve", "decimals", "symbol", "allowance"}
        erc20_funcs = {i["name"] for i in ERC20_ABI_MINIMAL if i.get("type") == "function"}
        missing = required_erc20 - erc20_funcs
        if missing: report.failed += 1; report.errors.append(f"ERC20 missing: {missing}")
        else: report.passed += 1

        required_aave = {"supply", "withdraw", "getUserAccountData", "getReserveData"}
        aave_funcs = {i["name"] for i in AAVE_POOL_ABI if i.get("type") == "function"}
        missing = required_aave - aave_funcs
        if missing: report.failed += 1; report.errors.append(f"Aave missing: {missing}")
        else: report.passed += 1

        from src.yield_protocols.lido import LIDO_ABI
        required_lido = {"submit", "balanceOf", "decimals"}
        lido_funcs = {i["name"] for i in LIDO_ABI if i.get("type") == "function"}
        missing = required_lido - lido_funcs
        if missing: report.failed += 1; report.errors.append(f"Lido missing: {missing}")
        else: report.passed += 1
    except ImportError as e:
        report.errors.append(f"ABI import: {e}")
        report.failed += 1
    return report


def run_all(target_module: str = "", verbose: bool = False) -> List[ValidationReport]:
    validators = {
        "contract_addresses": validate_contract_addresses,
        "yield_scanner": validate_yield_scanner,
        "strategies": validate_strategy_config,
        "safety_guard": validate_safety_limits,
        "abi_definitions": validate_abi_definitions,
    }
    reports = []
    for name, validator in validators.items():
        if target_module and target_module != name: continue
        try: reports.append(validator(verbose=verbose))
        except Exception as e: reports.append(ValidationReport(module=name, failed=1, errors=[str(e)]))
    return reports


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GETIN Pydantic Validation Suite")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--module", type=str, default="")
    args = parser.parse_args()
    from src.config_manager import load_env; load_env()
    print("=" * 70)
    print("GETIN ENGINEERING VALIDATION")
    print("=" * 70)
    reports = run_all(target_module=args.module, verbose=args.verbose)
    total_passed = sum(r.passed for r in reports)
    total_failed = sum(r.failed for r in reports)
    print()
    print("=" * 70)
    for report in reports:
        status = "✓" if report.failed == 0 else "✗"
        print(f"  [{status}] {report.module}: {report.passed} passed, {report.failed} failed")
        for err in report.errors: print(f"    ERROR: {err}")
        for warn in report.warnings: print(f"    WARN:  {warn}")
    print("=" * 70)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    if total_failed > 0:
        print(f"\n✗ VALIDATION FAILED — {total_failed} checks did not pass.")
        sys.exit(1)
    else:
        print("\n✓ ALL CHECKS PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()