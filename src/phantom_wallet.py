"""
Real Phantom Wallet integration for GETIN yield bot.

Supports:
  - Import Phantom wallet from base58 private key (the native Phantom format)
  - Export internal keypair to Phantom-compatible base58 key
  - Phantom mobile deep links for Send, Stake, Swap
  - QR code generation for mobile scanning
  - Balance queries for imported Phantom wallets

Phantom wallet format:
  - 64-byte keypair stored as base58 string
  - This is the format you get from Phantom -> Settings -> Export Private Key

Usage:
  from src.phantom_wallet import import_phantom, export_phantom, phantom_deep_link
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from solders.keypair import Keypair
from solders.pubkey import Pubkey

WALLET_DIR = "wallets"


def _ensure_wallet_dir() -> None:
    os.makedirs(WALLET_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Base58 encode/decode (Phantom's native key format)
# ---------------------------------------------------------------------------

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58_encode(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    result = ""
    while num > 0:
        num, rem = divmod(num, 58)
        result = _B58_ALPHABET[rem] + result
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return _B58_ALPHABET[0] * pad + result


def _b58_decode(s: str) -> bytes:
    num = 0
    for char in s:
        num = num * 58 + _B58_ALPHABET.index(char)
    result = num.to_bytes((num.bit_length() + 7) // 8, "big")
    pad = 0
    for char in s:
        if char == _B58_ALPHABET[0]:
            pad += 1
        else:
            break
    if pad:
        result = b"\x00" * pad + result
    return result


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------

def import_phantom(
    base58_private_key: str, name: str = "phantom"
) -> Keypair:
    """
    Import a Phantom wallet from its base58 private key.

    Phantom's native export format is a 64-byte keypair encoded as base58.
    To get your key: Phantom -> Settings -> Manage Wallets -> Export Private Key

    Args:
        base58_private_key: The base58 private key from Phantom
        name: Wallet name for storage

    Returns:
        The solders Keypair ready for signing transactions

    Raises:
        ValueError: If the key is invalid or wrong length
    """
    raw = base58_private_key.strip()
    secret = _b58_decode(raw)

    if len(secret) == 64:
        kp = Keypair.from_bytes(secret)
    elif len(secret) == 32:
        kp = Keypair.from_seed(secret)
    else:
        raise ValueError(
            f"Invalid Phantom key: expected 64 bytes (keypair) or 32 bytes (seed), "
            f"got {len(secret)} bytes. Check your Phantom export."
        )

    _ensure_wallet_dir()
    env_path = os.path.join(WALLET_DIR, f"{name}.env")
    with open(env_path, "w", encoding="utf-8") as fh:
        fh.write(f"SOLANA_PRIVATE_KEY={secret.hex()}\n")
    os.chmod(env_path, 0o600)

    meta = {
        "name": name,
        "address": str(kp.pubkey()),
        "chain": "solana",
        "wallet_type": "phantom",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = os.path.join(WALLET_DIR, f"{name}.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    pub = kp.pubkey()
    print(f"Phantom wallet imported: {name}")
    print(f"Address:   {pub}")
    print(f"Stored at: wallets/{name}.env  (chmod 600)")
    print()
    print("To verify in Phantom: go to Settings -> Manage Wallets -> Import Private Key")
    print(f"and paste this key: {base58_private_key}")
    return kp


def export_phantom(wallet_name: str = "solana_01") -> str:
    """
    Export an internal GETIN Solana wallet to Phantom-compatible base58 key.

    You can paste the output directly into Phantom's "Import Private Key" dialog.

    Args:
        wallet_name: Name of the wallet to export (default: solana_01)

    Returns:
        Base58-encoded private key string

    Raises:
        FileNotFoundError: If the wallet doesn't exist
        ValueError: If no private key is found
    """
    env_path = os.path.join(WALLET_DIR, f"{wallet_name}.env")
    if not os.path.isfile(env_path):
        raise FileNotFoundError(
            f"Wallet '{wallet_name}' not found at {env_path}. "
            "Generate one: python -m src.main --generate-solana-wallet {wallet_name}"
        )

    key_hex = os.getenv("SOLANA_PRIVATE_KEY")
    if not key_hex or key_hex == "0x00":
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("SOLANA_PRIVATE_KEY="):
                    key_hex = line.split("=", 1)[1].strip('"').strip("'")
                    break

    if not key_hex or key_hex == "0x00":
        raise ValueError(f"No private key found for wallet '{wallet_name}'")

    secret = bytes.fromhex(key_hex)
    base58_key = _b58_encode(secret)

    print()
    print("=" * 60)
    print(f"PHANTOM PRIVATE KEY — {wallet_name}")
    print("=" * 60)
    print(base58_key)
    print("=" * 60)
    print()
    print("KEEP THIS SECRET. Anyone with this key controls the wallet.")
    print()
    print("To import into Phantom:")
    print("  1. Open Phantom browser extension or mobile app")
    print("  2. Settings -> Manage Wallets -> Import Private Key")
    print("  3. Paste the key above")
    print()
    return base58_key


# ---------------------------------------------------------------------------
# Phantom deep links
# ---------------------------------------------------------------------------

def deep_link_transfer(to_address: str, amount_sol: float = 0.0) -> str:
    """Generate a Phantom `solana:` mobile deep link to send SOL."""
    if amount_sol > 0:
        return f"solana:{to_address}?amount={amount_sol}"
    return f"solana:{to_address}"


def deep_link_stake(pool: str = "jito") -> str:
    """Generate a Phantom deeplink to Jito stake or other LSTs."""
    jito_url = "https://www.jito.network/stake"
    return f"phantom://browse/{jito_url}?ref=getin"


def deep_link_swap(
    from_token: str = "So11111111111111111111111111111111111111112",
    to_token: str = "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
    amount_sol: float = 0.0,
) -> str:
    """Generate a Jupiter swap URL that Phantom can open."""
    params = f"inputMint={from_token}&outputMint={to_token}"
    if amount_sol > 0:
        params += f"&amount={int(amount_sol * 1e9)}"
    jup_url = f"https://jup.ag/swap/{from_token}-{to_token}?{params}"
    return f"phantom://browse/{jup_url}"


def show_qr_code(data: str, label: str = "phantom") -> None:
    """
    Display a QR code for the given data (address, URL, or deep link).
    If qrcode library is not installed, falls back to text-only output.
    """
    try:
        import qrcode as _qr

        qr = _qr.QRCode(version=1, box_size=3, border=3)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        qr_path = os.path.join(WALLET_DIR, f"{label}_qr.png")
        img.save(qr_path)
        print(f"\nQR code saved to: {qr_path}")
        print("Scan with Phantom mobile app to open this action.")
        print(f"URL: {data}")
    except ImportError:
        print("\n(qrcode library not installed — text output only)")
        print(f"URL: {data}")


# ---------------------------------------------------------------------------
# Balance queries
# ---------------------------------------------------------------------------

def get_phantom_balances(
    pubkey: str,
    rpc_url: str = "https://api.mainnet-beta.solana.com",
    known_mints: Optional[Dict[str, str]] = None,
) -> Dict[str, float]:
    """
    Query SOL balance and known SPL token balances for a Phantom wallet.

    Args:
        pubkey: Solana base58 address (from Phantom)
        rpc_url: Solana RPC endpoint
        known_mints: Optional dict of {token_name: mint_address}

    Returns:
        Dict with 'SOL' and token name -> balance mappings
    """
    import httpx

    if known_mints is None:
        known_mints = {
            "JITOSOL": "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
            "MSOL": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        }

    balances: Dict[str, float] = {"SOL": 0.0}
    client = httpx.Client(timeout=30.0)

    # SOL balance
    resp = client.post(
        rpc_url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [pubkey, {"commitment": "confirmed"}],
        },
    )
    resp.raise_for_status()
    balances["SOL"] = resp.json()["result"]["value"] / 1e9

    # Token balances
    for token_name, mint in known_mints.items():
        try:
            resp = client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        pubkey,
                        {"mint": mint},
                        {"encoding": "jsonParsed"},
                    ],
                },
            )
            resp.raise_for_status()
            accounts = resp.json()["result"]["value"]
            if accounts:
                info = accounts[0]["account"]["data"]["parsed"]["info"]
                raw = int(info["tokenAmount"]["amount"])
                decimals = info["tokenAmount"]["decimals"]
                balance = raw / (10 ** decimals)
                if balance > 0:
                    balances[token_name] = balance
        except Exception:
            pass

    return balances