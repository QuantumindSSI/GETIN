# GETIN — Yield Farming Agent

GETIN is a CLI agent and Telegram bot for automated DeFi yield farming.
It scans live yields, manages wallets, and executes on-chain deposits
into real mainnet protocols (Aave v3, Lido, JitoSOL).

No simulations. No demo trackers. No fabricated earnings.
Every command either executes real transactions or refuses.

---

## Quick Start

```bash
git clone https://github.com/QuantumindSSI/GETIN.git
cd GETIN
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set the required API keys in `.env`:
- `CRYPTORANK_API_KEY` — free from [CryptoRank](https://cryptorank.io/public-api/dashboard)
- `TELEGRAM_BOT_TOKEN` — from [BotFather](https://t.me/botfather) (if using Telegram)
- `KRAKEN_API_KEY` / `KRAKEN_API_SECRET` — for GBP on-ramp (if deploying real capital)
- `ETH_RPC_URL` — Ethereum RPC endpoint (default: `https://eth.drpc.org`)
- `SOL_RPC_URL` — Solana RPC endpoint (default: `https://api.mainnet-beta.solana.com`)

---

## Commands

### Wallet Management

Generate an Ethereum (BIP39) wallet:
```bash
python -m src.main --generate-wallet farming_wallet
```

Generate a Solana keypair:
```bash
python -m src.main --generate-solana-wallet solana_farming
```

Import a 12-word mnemonic:
```bash
python -m src.main --import-mnemonic my_wallet
```

Recovery phrases are written to `wallets/{name}_mnemonic.txt` with `chmod 600`.
They are never printed to stdout. All wallet files are gitignored.

### Market Intelligence

Live prices:
```bash
CRYPTORANK_API_KEY=your_key python -m src.main --currency-symbols BTC ETH SOL DOGE ADA
```

Global market snapshot:
```bash
CRYPTORANK_API_KEY=your_key python -m src.main --market
```

### DeFi Yield Scanner

Scan live Ethereum and Solana yields from DefiLlama — no API key required:
```bash
python -m src.main --yield-scan
```

ROI is calculated using compound APY formula: `amount * ((1 + APY)^(fraction) - 1)`.

### Real Capital Deployment

Deploy GBP into yield protocols via Kraken:
```bash
python -m src.main --invest --budget-gbp 100 --strategy conservative
```

This executes a market buy on Kraken, withdraws to your self-custody wallet,
and deposits into the strategy's allocated protocols (Aave, Lido, JitoSOL).

**DRY_RUN is on by default.** Set `DRY_RUN=false` in `.env` to execute real transactions.
Every transaction prompts for confirmation unless `--yes` is passed.

### Harvest Yield

Claim accrued yield from all active positions:
```bash
python -m src.main --harvest
```

### Check Positions

View current yield positions:
```bash
python -m src.main --positions --strategy conservative
```

### Exit All Protocols

Withdraw all funds back to wallet:
```bash
python -m src.main --unwind
```

---

## Telegram Bot

```bash
python -m src.telegram_bot
```

| Command | Action |
|---------|--------|
| `/yield` | Live DeFi yield scan |
| `/market` | Global market snapshot |
| `/prices BTC ETH` | Live prices |
| `/wallet` | Generate ETH wallet |
| `/solana_wallet` | Generate Solana wallet |
| `/invest conservative 100` | Deploy GBP 100 |
| `/harvest` | Claim yield |
| `/positions` | Show positions |
| `/unwind` | Exit all protocols |
| `/safety` | Safety limits and dry-run status |

---

## Supported Yield Protocols

| Protocol | Chain | Type |
|----------|-------|------|
| Aave v3 | Ethereum | Lending (WETH, USDC) |
| Lido | Ethereum | Liquid staking (stETH) |
| JitoSOL | Solana | Liquid staking |
| Marinade mSOL | Solana | Liquid staking |

### Strategy Configurations (`config/strategies.yaml`)

- **conservative** — 30% Lido, 20% Aave WETH, 50% JitoSOL
- **balanced** — 25% Lido, 25% Aave USDC, 50% JitoSOL
- **aggressive_solana** — 50% JitoSOL, 30% mSOL, 20% Kamino

---

## Project Structure

```
getin/
  config/
    rpc_endpoints.yaml
    strategies.yaml
  wallets/                  # Encrypted key storage (gitignored)
  .env                      # API keys (gitignored)
  src/
    main.py                 # CLI entry point
    telegram_bot.py          # Telegram bot
    cryptorank_client.py     # CryptoRank v3 API
    currency_monitor.py      # Live price tracker
    yield_scanner.py         # DefiLlama yield scanner
    wallet_setup.py          # ETH and SOL keypair generation
    wallet_manager.py        # Unified wallet interface
    safety_guard.py          # Safety limits and dry-run mode
    exchange_client.py       # Kraken REST client for GBP on-ramp
    portfolio_manager.py     # Strategy-based capital deployment
    harvester.py             # Automated yield harvesting
    transaction_monitor.py   # Ethereum tx receipt monitoring
    chain_clients/           # Ethereum and Solana RPC clients
    yield_protocols/         # Aave v3, Lido, Jupiter/JitoSOL modules
    validation/              # Pydantic engineering validation suite
```

---

## API Sources

| Source | Purpose | Key Required |
|--------|---------|--------------|
| [CryptoRank v3](https://cryptorank.io/public-api) | Market data | Yes (Sandbox tier is free) |
| [DefiLlama](https://yields.llama.fi) | Live DeFi APY and TVL | No |
| [Kraken](https://api.kraken.com) | Fiat on-ramp (GBP → crypto) | Yes |
| [Jupiter v6](https://quote-api.jup.ag/v6) | Solana token swaps | No |

---

## Requirements

- Python 3.10+
- A CryptoRank API key (Sandbox tier is free)
- A Kraken API key (for GBP → crypto on-ramp)
- An Ethereum RPC endpoint and funded wallet for real deployment
- A Solana RPC endpoint and funded wallet for Solana yield

```bash
pip install -r requirements.txt
```

## License

MIT