# GETIN — Cryptocurrency Farming Agent

GETIN automates testnet participation, DeFi yield monitoring, and currency
tracking. One CLI agent manages wallets, scans live yields, watches markets,
and logs every on-chain action for airdrop eligibility.

---

## Quick Start

```bash
git clone https://github.com/QuantumindSSI/GETIN.git
cd GETIN
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy the environment template
cp .env.example .env
```

Set `CRYPTORANK_API_KEY` in `.env`. Get a free Sandbox key from the
[CryptoRank dashboard](https://cryptorank.io/public-api/dashboard).

---

## Commands

### Wallet Management

Generate a fresh Ethereum (BIP39) wallet:

```bash
python -m src.main --generate-wallet farming_wallet
```

Generate a fresh Solana keypair (for Phantom or Solflare):

```bash
python -m src.main --generate-solana-wallet solana_farming
```

Import a 12-word mnemonic from Trust Wallet or Phantom:

```bash
python -m src.main --import-mnemonic my_wallet
```

The agent derives the Ethereum private key at `m/44'/60'/0'/0/0`.
All keys are stored under `wallets/` with chmod 600 and never leave the
machine. The `wallets/` directory is gitignored.

### Market Intelligence

Live price and market cap for any symbols:

```bash
CRYPTORANK_API_KEY=your_key python -m src.main --currency-symbols BTC ETH SOL DOGE ADA
```

```
BTC: $64837.58 | MCap: $1300822328222.21
ETH: $1919.76 | MCap: $231679426944.20
SOL: $74.43 | MCap: $43138795589.53
```

Global crypto market snapshot:

```bash
CRYPTORANK_API_KEY=your_key python -m src.main --market
```

Outputs total market cap, 24h volume, BTC/ETH dominance, active currencies,
and 24h change percent.

### DeFi Yield Scanner

Scan live Ethereum and Solana DeFi yields with per-6-hour and 30-day ROI
projections:

```bash
python -m src.main --yield-scan
```

```
Protocol                         Asset       APY %            TVL     6h ROI/$1000   30d ROI/$1000
Aave v3 ETH                      WETH        1.51%  $4,376,807         0.0104           1.24
Aave v3 USDC                     USDC        2.35%  $1,767,811         0.0161           1.93
Lido stETH                       STETH       2.28% $17,992,367,560     0.0156           1.88
JitoSOL (Solana)                 JITOSOL     5.14% $739,806,006        0.0352           4.22
Marinade mSOL (Solana)           MSOL        4.79% $175,960,025        0.0328           3.93
Orca SOL/USDC LP                 SOL-USDC    7.83% $15,854             0.0537           6.44
```

The scanner uses the DefiLlama API. No API key is required. Rates are live
and change daily. The ROI formula is:

```
amount * (APY / 100 / 365 / 24) * hours
```

### Testnet Activities Reference

List every known farming activity across Monad, Berachain, Somnia, and
Solana devnet (149 activities total):

```bash
python -m src.main --activities
```

Each project is broken down by category: faucets, DEX swaps, staking,
lending, NFT mints, bridges, daily check-ins, quest platforms, games, and
other interactions. Every entry includes the URL, cooldown period, and
notes.

### Watchlist Management

Refresh the watchlist using CryptoRank funding and token-unlock data:

```bash
CRYPTORANK_API_KEY=your_key python -m src.main --refresh
```

The agent pulls VC funding rounds and upcoming token unlocks. It drops any
project that already has a live token. The output is written to
`ranked_watchlist.json`. Endpoints that require higher plan tiers are
skipped gracefully.

### Task Execution Loop

Run the automated farming loop:

```bash
CRYPTORANK_API_KEY=your_key python -m src.main \
  --run-tasks \
  --wallet farming_wallet \
  --rpc https://rpc.ankr.com/eth
```

The scheduler reads the ranked watchlist and executes each action in
sequence. Delays between actions are randomized (45 to 180 seconds).
Every transaction is logged to `activity_log.jsonl` with its hash,
project name, action, and timestamp.

### TGE and Token Unlock Alerts

Check for token generation events and unlock notices on watched projects:

```bash
CRYPTORANK_API_KEY=your_key python -m src.main --check-tge
```

Matching events are printed as alerts. The bot does **not** auto-claim
any tokens. Claim pages are the most common phishing vector in this space.
Verify every claim link manually before interacting.

---

## Solana Zero-Capital Farming

GETIN includes a complete zero-capital workflow for Solana. You can start
farming with exactly $0.

1.  Generate a Solana wallet: `python -m src.main --generate-solana-wallet`
2.  Import the hex key into Phantom or Solflare
3.  Request free Devnet SOL from [solfaucet.com](https://solfaucet.com)
4.  Switch Phantom to Devnet and practice on Orca, Raydium, and Kamino
    (free test versions)
5.  Earn real mainnet tokens ($0 cost) through Layer3, Zealy, Galxe, and
    Superteam bounties
6.  Deploy earned tokens into mainnet yield pools. Compound at live APY
    rates shown by `--yield-scan`

The full step-by-step guide is inside `config/testnet_activities.yaml`
under the Solana section.

---

## Project Structure

```
getin/
  config/
    rpc_endpoints.yaml          # RPC endpoint reference
    testnet_activities.yaml     # 149 farming activities across 4 chains
  wallets/                      # Encrypted key storage (gitignored)
  watchlist.yaml                # Seed testnet list for the agent
  ranked_watchlist.json         # Auto-generated ranked watchlist
  activity_log.jsonl            # On-chain action audit trail
  .env                          # API key and private key (gitignored)
  src/
    main.py                     # CLI entry point
    cryptorank_client.py        # CryptoRank v3 API client
    currency_monitor.py         # Live price and market cap tracker
    yield_scanner.py            # DeFi yield scanner (DefiLlama)
    refresh_watchlist.py        # VC funding and unlock cross-reference
    task_scheduler.py           # Farming loop with randomized delays
    wallet_manager.py           # Web3 transaction signing
    wallet_setup.py             # ETH and SOL keypair generation
    tge_monitor.py              # Token unlock event watcher
    logger.py                   # JSON Lines activity logger
    config_manager.py           # YAML and .env loader
```

---

## Security

The agent follows these rules:

| Rule | Behaviour |
|---|---|
| Private keys | Stored in `wallets/` with chmod 600, never committed |
| API keys | Read from `.env` only, `.gitignore` blocks the file |
| Third-party APIs | CryptoRank is used for read-only market data only |
| Auto-claims | Deliberately omitted to avoid phishing risks |
| Wallet isolation | Use a dedicated wallet with zero real assets |

### Before You Run the Task Loop

- [ ] The farming wallet holds zero real assets
- [ ] The `.env` file is gitignored
- [ ] The API key is not committed to any public repo
- [ ] You confirm each project is from its official Discord or docs
- [ ] Token approvals are limited to single transactions (no unlimited
      `approve()` calls)
- [ ] You understand airdrop rewards are speculative

---

## Requirements

- Python 3.10 or later
- A CryptoRank API key (Sandbox tier is free)
- Optional: an Ethereum RPC endpoint and a testnet wallet for the task
  loop
- Optional: a Phantom or Solflare wallet for Solana devnet farming

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Dependencies: `requests`, `PyYAML`, `python-dotenv`, `web3`, `solders`,
`solana`.

---

## API Sources

| Source | Purpose | Key Required |
|---|---|---|
| [CryptoRank v3](https://cryptorank.io/public-api) | Market data, funding rounds, TGE alerts | Yes (Sandbox is free) |
| [DefiLlama](https://yields.llama.fi) | Live DeFi APY and TVL | No |

---

## License

MIT