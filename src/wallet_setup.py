import os
import json
from datetime import datetime, timezone
from typing import Optional

from eth_account import Account
from eth_account.signers.local import LocalAccount
from solders.keypair import Keypair


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
    print(f"Recovery phrase written to: wallets/{name}_mnemonic.txt (chmod 600)")
    print("STORE THIS FILE OFFLINE AND DELETE IT FROM DISK WHEN SAFE.")
    # Write mnemonic to a separate file — NEVER print to stdout
    mnemonic_path = os.path.join(WALLET_DIR, f"{name}_mnemonic.txt")
    with open(mnemonic_path, "w", encoding="utf-8") as fh:
        fh.write(mnemonic)
    os.chmod(mnemonic_path, 0o600)
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


def generate_solana_wallet(name: str = "solana_01") -> str:
    """Create a fresh Solana keypair and save the private key."""
    kp = Keypair()
    # to_bytes() returns 64 bytes (seed + pubkey), compatible with from_bytes()
    secret = kp.to_bytes()

    _ensure_wallet_dir()
    env_path = os.path.join(WALLET_DIR, f"{name}.env")
    meta_path = os.path.join(WALLET_DIR, f"{name}.json")

    with open(env_path, "w", encoding="utf-8") as fh:
        fh.write(f"SOLANA_PRIVATE_KEY={secret.hex()}\n")
    os.chmod(env_path, 0o600)

    meta = {
        "name": name,
        "address": str(kp.pubkey()),
        "chain": "solana",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"Solana wallet generated: {name}")
    print(f"Address: {kp.pubkey()}")
    print(f"Private key (128 hex) saved to: {env_path}")
    print()
    print("For Phantom or Solflare import, use the address above to 'watch'")
    print("or send SOL from another wallet. The hex format is for internal")
    print("GETIN use only — Phantom/Solflare expect base58 keypairs or mnemonics.")
    return str(kp.pubkey())


def load_account(private_key: Optional[str] = None, name: str = "wallet_01") -> LocalAccount:
    """Load an account from env vars or a named wallet file."""
    key = private_key or os.getenv("PRIVATE_KEY")
    if not key or key == "0x00":
        env_path = os.path.join(WALLET_DIR, f"{name}.env")
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("PRIVATE_KEY="):
                        key = line.split("=", 1)[1].strip('"').strip("'")
                        break
    if not key or key == "0x00":
        raise ValueError("PRIVATE_KEY is missing. Use --generate-wallet first.")
    return Account.from_key(key)