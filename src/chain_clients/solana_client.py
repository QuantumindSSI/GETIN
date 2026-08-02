import base64
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.system_program import TransferParams, transfer

from src.safety_guard import SafetyGuard, SafetyError

SOL_MINT = "So11111111111111111111111111111111111111112"
JITOSOL_MINT = "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"
MSOL_MINT = "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"

ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")


def _find_associated_token_address(owner: Pubkey, mint: Pubkey) -> Pubkey:
    from solders.pubkey import Pubkey
    seeds = [bytes(owner), bytes(TOKEN_PROGRAM_ID), bytes(mint)]
    addr, _ = Pubkey.find_program_address(seeds, ASSOCIATED_TOKEN_PROGRAM_ID)
    return addr


def _make_associated_token_account_ix(payer: Pubkey, owner: Pubkey, mint: Pubkey):
    ata = _find_associated_token_address(owner, mint)
    keys = [
        {"pubkey": payer, "isSigner": True, "isWritable": True},
        {"pubkey": ata, "isSigner": False, "isWritable": True},
        {"pubkey": owner, "isSigner": False, "isWritable": False},
        {"pubkey": mint, "isSigner": False, "isWritable": False},
        {"pubkey": SYSTEM_PROGRAM_ID, "isSigner": False, "isWritable": False},
        {"pubkey": TOKEN_PROGRAM_ID, "isSigner": False, "isWritable": False},
    ]
    return {"program_id": ASSOCIATED_TOKEN_PROGRAM_ID, "keys": keys, "data": bytes(0)}


SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")


def _instruction_from_dict(d: Dict[str, Any]):
    from solders.instruction import Instruction, AccountMeta
    return Instruction(
        keys=[AccountMeta(pubkey=k["pubkey"], is_signer=k["isSigner"], is_writable=k["isWritable"]) for k in d["keys"]],
        program_id=d["program_id"],
        data=d["data"],
    )


class SolanaRpcClient:
    """Minimal synchronous Solana JSON-RPC client using httpx."""

    def __init__(self, endpoint: str, timeout: float = 30.0):
        self.endpoint = endpoint
        self.http = httpx.Client(timeout=timeout)
        self._req_id = 0

    def _call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        self._req_id += 1
        payload = {"jsonrpc": "2.0", "id": self._req_id, "method": method, "params": params or []}
        resp = self.http.post(self.endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Solana RPC error: {data['error']}")
        return data["result"]

    def get_balance(self, pubkey: Pubkey) -> int:
        return self._call("getBalance", [str(pubkey), {"commitment": "confirmed"}])["value"]

    def get_account_info(self, pubkey: Pubkey):
        return self._call("getAccountInfo", [str(pubkey), {"encoding": "jsonParsed", "commitment": "confirmed"}])

    def get_token_account_balance(self, pubkey: Pubkey):
        return self._call("getTokenAccountBalance", [str(pubkey), {"commitment": "confirmed"}])

    def get_latest_blockhash(self):
        return self._call("getLatestBlockhash", [{"commitment": "confirmed"}])

    def send_transaction(self, signed_tx: VersionedTransaction) -> str:
        serialized = signed_tx.serialize()
        b64_tx = base64.b64encode(serialized).decode("ascii")
        result = self._call("sendTransaction", [b64_tx, {"encoding": "base64", "preflightCommitment": "confirmed", "skipPreflight": False}])
        return result

    def get_signature_statuses(self, signatures: List[str]):
        return self._call("getSignatureStatuses", [signatures])

    def confirm_transaction(self, signature: str, timeout: int = 60):
        start = time.time()
        while time.time() - start < timeout:
            result = self.get_signature_statuses([signature])
            value = result.get("value", [])
            if value and value[0]:
                confs = value[0].get("confirmationStatus")
                if confs in ("confirmed", "finalized"):
                    if value[0].get("err"):
                        raise RuntimeError(f"Transaction failed: {value[0]['err']}")
                    return
            time.sleep(2)
        raise TimeoutError(f"Transaction {signature} not confirmed within {timeout}s")


class SolanaClient:
    """
    Production-grade Solana client with versioned transaction support.
    """

    def __init__(
        self,
        rpc_url: str = "https://api.mainnet-beta.solana.com",
        wallet_name: str = "solana_01",
        guard: Optional[SafetyGuard] = None,
    ):
        self.rpc = SolanaRpcClient(rpc_url)
        self.keypair = self._load_keypair(wallet_name)
        self.guard = guard or SafetyGuard()

    def _load_keypair(self, name: str) -> Keypair:
        env_path = os.path.join("wallets", f"{name}.env")
        key_hex: Optional[str] = os.getenv("SOLANA_PRIVATE_KEY")
        if not key_hex or key_hex == "0x00":
            key_hex = None
            if os.path.isfile(env_path):
                with open(env_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith("SOLANA_PRIVATE_KEY="):
                            key_hex = line.split("=", 1)[1].strip('"').strip("'")
                            break
        if not key_hex or key_hex == "0x00":
            raise ValueError(f"No Solana private key found for wallet '{name}'. Generate one with --generate-solana-wallet")
        secret = bytes.fromhex(key_hex)
        if len(secret) == 64:
            return Keypair.from_bytes(secret)
        elif len(secret) == 32:
            return Keypair.from_seed(secret)
        else:
            raise ValueError(f"Unexpected Solana key length: {len(secret)} bytes (expected 32 or 64)")

    @property
    def pubkey(self) -> Pubkey:
        return self.keypair.pubkey()

    @property
    def address(self) -> str:
        return str(self.pubkey)

    def get_balance(self) -> float:
        lamports = self.rpc.get_balance(self.pubkey)
        return lamports / 1e9

    def get_token_balance(self, mint: str) -> float:
        mint_pk = Pubkey.from_string(mint)
        ata = _find_associated_token_address(self.pubkey, mint_pk)
        try:
            resp = self.rpc.get_token_account_balance(ata)
            value = resp.get("value", {})
            ui = value.get("uiAmount")
            if ui is not None:
                return float(ui)
            raw = int(value.get("amount", 0))
            decimals = int(value.get("decimals", 9))
            return raw / (10 ** decimals)
        except Exception:
            return 0.0

    def send_legacy_transaction(
        self,
        instructions: list,
        signers: Optional[list] = None,
        compute_units: Optional[int] = None,
        unit_price_micro_lamports: Optional[int] = None,
        skip_preflight: bool = False,
    ) -> str:
        from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
        ix_list = list(instructions)
        if compute_units:
            ix_list.insert(0, set_compute_unit_limit(compute_units))
        if unit_price_micro_lamports:
            ix_list.insert(0, set_compute_unit_price(unit_price_micro_lamports))

        blockhash_resp = self.rpc.get_latest_blockhash()
        blockhash = blockhash_resp["value"]["blockhash"]
        from solders.pubkey import Pubkey
        from solders.hash import Hash
        message = MessageV0.try_compile(
            self.pubkey,
            ix_list,
            [],
            Hash.from_string(blockhash),
        )
        txn = VersionedTransaction(message, [self.keypair])

        # AI sanitisation of on-chain transaction
        from src.ai_sanitizer import get_ai_sanitizer
        ai_check = get_ai_sanitizer().sanitise_transaction(
            action="send_legacy_transaction",
            protocol="solana",
            chain="solana",
            amount=None,
            contract_address=None,
            extra={"instructions": len(ix_list)},
        )
        if not ai_check.is_safe:
            raise SafetyError(f"AI safety check failed: {ai_check.warnings}")
        for w in ai_check.warnings:
            print(f"[AI WARNING] {w}")

        sig = self.rpc.send_transaction(txn)
        self.rpc.confirm_transaction(sig)
        return sig

    def transfer_sol(self, to: str, amount_sol: float) -> str:
        to_pk = Pubkey.from_string(to)
        lamports = int(amount_sol * 1e9)
        if lamports <= 0:
            raise SafetyError("Transfer amount must be positive.")
        ix = transfer(
            TransferParams(
                from_pubkey=self.pubkey,
                to_pubkey=to_pk,
                lamports=lamports,
            )
        )
        if self.guard.is_dry_run():
            print(f"[DRY RUN] Would send {amount_sol} SOL to {to}")
            return "DRYRUN"

        if not self.guard.confirm("SOL Transfer", f"Send {amount_sol} SOL to {to}?"):
            raise SafetyError("User aborted SOL transfer.")

        self.guard.check_min_trade_sol(amount_sol)
        return self.send_legacy_transaction([ix])

    def ensure_associated_token_account(self, mint: str) -> str:
        mint_pk = Pubkey.from_string(mint)
        ata = _find_associated_token_address(self.pubkey, mint_pk)
        info = self.rpc.get_account_info(ata)
        if info.get("value") is None:
            # Create ATA
            keys = [
                (self.pubkey, True, True),
                (ata, False, True),
                (self.pubkey, False, False),
                (mint_pk, False, False),
                (SYSTEM_PROGRAM_ID, False, False),
                (TOKEN_PROGRAM_ID, False, False),
            ]
            from solders.instruction import Instruction, AccountMeta
            ix = Instruction(
                keys=[AccountMeta(pubkey=k[0], is_signer=k[1], is_writable=k[2]) for k in keys],
                program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
                data=bytes(),
            )
            sig = self.send_legacy_transaction([ix])
            print(f"  Created ATA for {mint}: {ata} (tx {sig})")
        return str(ata)
