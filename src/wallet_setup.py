import os
import json
from datetime import datetime, timezone
from typing import Optional

from eth_account import Account
from eth_account.signers.local import LocalAccount


Account.enable_unaudited_hdwallet_features()

TRUST_WALLET_PATH = "m/44'/60'/0'/0/0"
WALLET_DIR = "wallets"


def _ensure_wallet_dir() -> None:
    """Create the wallet directory if it does not exist."""
    os.makedirs(WALLET_DIR, exist_ok=True)


def generate_wallet(name: str = "wallet_01") -> str:
    """Create a fresh BIP39 wallet and save the private key."""
    acct, mnemonic = Account.create_with_mnemonic()

    _ensure_wallet_dir()
    env_path = os.path.join(WALLET_DIR, f"{name}.env")
    meta_path = os.path.join(WALLET_DIR, f"{name}.json")

    with open(env_path, "w", encoding="utf-8") as fh:
        fh.write(f"PRIVATE_KEY={acct.key.hex()}\n")
    os.chmod(env_path, 0o600)

    meta = {
        "name": name,
        "address": acct.address,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "derivation_path": TRUST_WALLET_PATH,
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"Wallet generated: {name}")
    print(f"Address: {acct.address}")
    print(f"Private key saved to: {env_path}")
    print()
    print("Mnemonic (12 words) — store this offline, never share:")
    print(mnemonic)
    return acct.address


def import_mnemonic(mnemonic: str, name: str = "wallet_01") -> str:
    """Derive the private key from a 12-word mnemonic and save it."""
    acct = Account.from_mnemonic(mnemonic, account_path=TRUST_WALLET_PATH)

    _ensure_wallet_dir()
    env_path = os.path.join(WALLET_DIR, f"{name}.env")
    meta_path = os.path.join(WALLET_DIR, f"{name}.json")

    with open(env_path, "w", encoding="utf-8") as fh:
        fh.write(f"PRIVATE_KEY={acct.key.hex()}\n")
    os.chmod(env_path, 0o600)

    meta = {
        "name": name,
        "address": acct.address,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "derivation_path": TRUST_WALLET_PATH,
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"Wallet imported: {name}")
    print(f"Address: {acct.address}")
    print(f"Private key stored at: {env_path}")
    return acct.address


def load_account(private_key: Optional[str] = None, name: str = "wallet_01") -> LocalAccount:
    """Load an account from env vars or a named wallet file."""
    key = private_key or os.getenv("PRIVATE_KEY")
    if not key:
        env_path = os.path.join(WALLET_DIR, f"{name}.env")
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("PRIVATE_KEY="):
                        key = line.split("=", 1)[1].strip('"').strip("'")
                        break
    if not key:
        raise ValueError("PRIVATE_KEY is missing. Use --generate-wallet first.")
    return Account.from_key(key)