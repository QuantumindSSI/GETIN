import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

COMPLETED_FILE = "completed_quests.json"
EARNINGS_FILE = "earnings.json"

# Curated quests that are verified to exist and pay real tokens.
# Updated: July 2026. Rewards are approximate minimums.

QUEST_CATALOG: List[Dict[str, Any]] = [
    # --- BEGINNER: zero capital, no wallet needed ---
    {
        "id": "S1",
        "title": "Superteam Earn — First Bounty",
        "platform": "Superteam",
        "category": "beginner",
        "reward": 50.0,
        "reward_token": "USDC",
        "difficulty": "easy",
        "estimated_minutes": 15,
        "url": "https://earn.superteam.fun/",
        "steps": [
            "Go to earn.superteam.fun",
            "Connect your Solana wallet (Phantom or Solflare)",
            "Filter by 'Beginner' difficulty",
            "Pick a bounty titled 'Write a tweet' or 'Design a meme'",
            "Follow the instructions exactly",
            "Submit your work before the deadline",
            "Receive USDC to your wallet within 7 days",
        ],
        "requires": ["Phantom or Solflare wallet", "Twitter account"],
        "cost": 0,
    },
    {
        "id": "L1",
        "title": "Layer3 — First Quest (Intro to Crypto)",
        "platform": "Layer3",
        "category": "beginner",
        "reward": 2.0,
        "reward_token": "OP/ARB/SCROLL",
        "difficulty": "easy",
        "estimated_minutes": 5,
        "url": "https://app.layer3.xyz/quests",
        "steps": [
            "Go to app.layer3.xyz/quests",
            "Sign up with email or wallet",
            "Find a quest labeled 'Free' or 'No gas'",
            "Complete the quiz or social action",
            "Claim your reward token",
        ],
        "requires": ["Email or wallet"],
        "cost": 0,
    },
    {
        "id": "G1",
        "title": "Galxe — Join a Solana Campaign",
        "platform": "Galxe",
        "category": "beginner",
        "reward": 1.0,
        "reward_token": "Project Token",
        "difficulty": "easy",
        "estimated_minutes": 5,
        "url": "https://app.galxe.com/",
        "steps": [
            "Go to app.galxe.com",
            "Search for 'Solana' in the campaigns",
            "Pick a campaign with OAT rewards",
            "Complete the social tasks (follow, retweet, join Discord)",
            "Claim your OAT/NFT badge",
        ],
        "requires": ["Discord account", "Twitter account"],
        "cost": 0,
    },
    # --- INTERMEDIATE: needs a wallet with devnet/testnet ---
    {
        "id": "S2",
        "title": "Superteam Earn — Bug Bounty (Low)",
        "platform": "Superteam",
        "category": "intermediate",
        "reward": 100.0,
        "reward_token": "USDC",
        "difficulty": "medium",
        "estimated_minutes": 60,
        "url": "https://earn.superteam.fun/bounties",
        "steps": [
            "Go to earn.superteam.fun/bounties",
            "Filter by 'Bug Bounty' and 'Low' difficulty",
            "Read the bounty description carefully",
            "Test the dApp on devnet (use free faucet SOL)",
            "Write a clear bug report with screenshots",
            "Submit through the platform",
            "Receive USDC if your report is accepted",
        ],
        "requires": ["Phantom wallet (devnet)", "Basic QA skills"],
        "cost": 0,
    },
    {
        "id": "L2",
        "title": "Layer3 — Daily Streak (7-day)",
        "platform": "Layer3",
        "category": "intermediate",
        "reward": 5.0,
        "reward_token": "OP/ARB/SCROLL",
        "difficulty": "easy",
        "estimated_minutes": 5,
        "url": "https://app.layer3.xyz/quests",
        "steps": [
            "Go to app.layer3.xyz",
            "Complete one free quest per day for 7 days",
            "Day 7 bonus: streak multiplier reward",
            "Claim all accumulated tokens",
        ],
        "requires": ["Email or wallet"],
        "cost": 0,
    },
    {
        "id": "M1",
        "title": "Monad Testnet — First Swap",
        "platform": "Monad Testnet",
        "category": "intermediate",
        "reward": 0.0,
        "reward_token": "Potential airdrop (MON)",
        "difficulty": "easy",
        "estimated_minutes": 10,
        "url": "https://app.uniswap.org/swap",
        "steps": [
            "Get free testnet MON from testnet.monad.xyz",
            "Go to app.uniswap.org, switch to Monad Testnet network",
            "Swap 0.1 MON for any token pair",
            "Record the tx hash for eligibility proof",
        ],
        "requires": ["EVM wallet (MetaMask/Trust)"],
        "cost": 0,
    },
    {
        "id": "B1",
        "title": "Berachain — Mint HONEY Stablecoin",
        "platform": "Berachain Testnet",
        "category": "intermediate",
        "reward": 0.0,
        "reward_token": "Potential airdrop (BERA)",
        "difficulty": "easy",
        "estimated_minutes": 15,
        "url": "https://bartio.honey.berachain.com/",
        "steps": [
            "Get free BERA from bartio.faucet.berachain.com",
            "Bridge stgUSDC via bridge.berachain.com",
            "Go to bartio.honey.berachain.com",
            "Mint HONEY with your stgUSDC",
            "Supply HONEY on Bend (bartio.bend.berachain.com)",
        ],
        "requires": ["EVM wallet", "0.001 ETH on mainnet (bridge fee)"],
        "cost": 1.0,
    },
    # --- ADVANCED: requires skills and time ---
    {
        "id": "S3",
        "title": "Superteam Earn — Content Writer",
        "platform": "Superteam",
        "category": "advanced",
        "reward": 200.0,
        "reward_token": "USDC",
        "difficulty": "hard",
        "estimated_minutes": 120,
        "url": "https://earn.superteam.fun/",
        "steps": [
            "Go to earn.superteam.fun",
            "Filter by 'Content' category",
            "Pick a bounty: write a thread, blog post, or tutorial",
            "Research the topic thoroughly",
            "Write 800-1500 word post with original insights",
            "Post on Twitter or submit as PDF",
            "Receive USDC within 14 days if accepted",
        ],
        "requires": ["Solana wallet", "Writing skills", "Twitter account"],
        "cost": 0,
    },
    {
        "id": "L3",
        "title": "Layer3 — Ecosystem Sprint (30-day)",
        "platform": "Layer3",
        "category": "advanced",
        "reward": 20.0,
        "reward_token": "Multiple tokens",
        "difficulty": "hard",
        "estimated_minutes": 300,
        "url": "https://app.layer3.xyz/quests",
        "steps": [
            "Go to app.layer3.xyz",
            "Join an active ecosystem sprint",
            "Complete all quests in the sprint over 30 days",
            "Claim the cumulative reward pool",
        ],
        "requires": ["Wallet", "Daily commitment (10 min/day)"],
        "cost": 0,
    },
    {
        "id": "A1",
        "title": "All Testnets — 30-day Rotation",
        "platform": "Multi-chain",
        "category": "advanced",
        "reward": 0.0,
        "reward_token": "Multiple airdrops (MON, BERA, Somnia)",
        "difficulty": "medium",
        "estimated_minutes": 300,
        "url": "https://t.me/yieldabot",
        "steps": [
            "Day 1-10 Monad: faucet, swap, stake (aPriori), LP (BeanSwap), NFT mint",
            "Day 11-20 Berachain: faucet, BEX swap, HONEY mint, Bend supply, BGT delegate",
            "Day 21-30 Somnia: faucet, staking dashboard, quest.somnia.network quests",
            "Use this bot to track tx hashes for eligibility proof",
        ],
        "requires": ["EVM wallet (testnet only)", "Daily 10 minutes"],
        "cost": 0,
    },
    # ---- AI-completable quests (20 new entries) ----
    {"id":"GQ1","title":"Galxe — Auto-scan Solana Campaigns","platform":"Galxe","category":"intermediate","reward":10.0,"reward_token":"Points/Tokens","difficulty":"easy","estimated_minutes":1,"url":"https://app.galxe.com/","steps":["Set GALXE_ACCESS_TOKEN in .env from dashboard.galxe.com","Run /auto_quest — the bot scans all active Solana campaigns","Bot checks wallet eligibility via GraphQL API","Bot marks which quests are completable via on-chain actions","No human clicks needed — API-only operation"],"requires":["Galxe access token","Solana/EVM wallet"],"cost":0},
    {"id":"ZF1","title":"Zerion — Auto-bridge across chains","platform":"Zerion","category":"intermediate","reward":0.0,"reward_token":"Airdrop eligibility","difficulty":"easy","estimated_minutes":2,"url":"https://api.zerion.io/v1/swap/quotes/","steps":["Set ZERION_API_KEY in .env from dashboard.zerion.io","Run /auto_quest — bot gets cross-chain swap quotes","Bot signs and broadcasts bridge transactions","Repeat across multiple chain pairs","Earn airdrop eligibility from protocol retroactive rewards"],"requires":["Zerion API key","EVM wallet with small gas balance"],"cost":1.0},
    {"id":"MO1","title":"Monad Testnet — Auto-rotation swap+stake+deploy","platform":"Monad Testnet","category":"advanced","reward":0.0,"reward_token":"Potential MON airdrop","difficulty":"medium","estimated_minutes":5,"url":"https://testnet.monad.xyz/","steps":["Ensure wallet has testnet MON from faucet","Run /auto_quest — bot connects to Monad RPC","Bot executes swap on DEX","Bot stakes MON to liquid staking protocol","Bot deploys a minimal smart contract","Repeat daily for maximum activity breadth"],"requires":["EVM wallet","Faucet MON (free)"],"cost":0},
    {"id":"BR1","title":"Berachain — Auto rotation swap+stake+mint","platform":"Berachain Testnet","category":"advanced","reward":0.0,"reward_token":"Potential BERA airdrop","difficulty":"medium","estimated_minutes":5,"url":"https://bartio.bex.berachain.com/","steps":["Ensure wallet has testnet BERA from faucet","Run /auto_quest — bot connects to Berachain RPC","Bot executes swap on BEX","Bot mints HONEY stablecoin","Bot stakes BERA for liquid staking","Bot deploys minimal smart contract"],"requires":["EVM wallet","Faucet BERA (free)"],"cost":0},
    {"id":"SM1","title":"Somnia — Auto rotation stake+deploy","platform":"Somnia Testnet","category":"advanced","reward":0.0,"reward_token":"Potential airdrop","difficulty":"easy","estimated_minutes":5,"url":"https://testnet.somnia.network/","steps":["Ensure wallet has testnet STT from faucet","Run /auto_quest — bot connects to Somnia RPC","Bot stakes STT to validator via staking dashboard","Bot deploys minimal smart contract"],"requires":["EVM wallet","Faucet STT (free)"],"cost":0},
    {"id":"AQ1","title":"Auto-faucet rotation all 3 testnets","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"Testnet tokens (free gas)","difficulty":"easy","estimated_minutes":2,"url":"https://t.me/yieldabot","steps":["Run /auto_quest — bot checks wallet balances","Bot identifies faucets with expired cooldowns","Bot sends claim requests to available faucets","Bot receives free testnet tokens","Repeat on 12h/24h cycles"],"requires":["EVM wallet","No capital needed"],"cost":0},
    {"id":"CV1","title":"Deploy contract on all 3 testnets","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"Airdrop eligibility","difficulty":"easy","estimated_minutes":2,"url":"https://t.me/yieldabot","steps":["Run /auto_quest — bot deploys minimal contracts","Deployed to Monad Berachain and Somnia testnets","Each deployment is a unique on-chain interaction","Multiple deployments improve airdrop qualification"],"requires":["EVM wallet","Faucet tokens (free)"],"cost":0},
    {"id":"GR1","title":"Grass — Auto bandwidth sharing node","platform":"Grass","category":"advanced","reward":5.0,"reward_token":"GRASS tokens (confirmed)","difficulty":"easy","estimated_minutes":1,"url":"https://www.grassfoundation.io/","steps":["Install the Grass desktop app or browser extension","Run it in the background 24/7","You earn GRASS tokens for unused bandwidth","Fully passive — no clicks after setup","Bot can monitor earnings via Grass API"],"requires":["Desktop or VPS","Internet connection"],"cost":0},
    {"id":"TP1","title":"Tea Protocol — Register OSS repo","platform":"Tea Protocol","category":"advanced","reward":50.0,"reward_token":"TEA tokens (confirmed)","difficulty":"medium","estimated_minutes":5,"url":"https://app.tea.xyz/","steps":["Go to app.tea.xyz and connect wallet","Register your open-source GitHub repo","Tea Protocol auto-calculates your teaRank","Stake TEA tokens on your project for rewards","Higher ecosystem impact = higher rewards"],"requires":["GitHub repo","Crypto wallet"],"cost":0},
    {"id":"TP2","title":"Tea Protocol — Stake TEA for rewards","platform":"Tea Protocol","category":"advanced","reward":10.0,"reward_token":"TEA tokens (staking yield)","difficulty":"easy","estimated_minutes":2,"url":"https://app.tea.xyz/","steps":["Acquire TEA tokens (earned from TP1 or bought)","Go to app.tea.xyz/staking","Stake TEA on high-ranked OSS projects","Earn continuous staking rewards","Fully automatable via smart contract interaction"],"requires":["TEA tokens","Crypto wallet"],"cost":20.0},
    {"id":"GL1","title":"Galxe — Auto-claim eligible points","platform":"Galxe","category":"intermediate","reward":5.0,"reward_token":"Loyalty points + tokens","difficulty":"easy","estimated_minutes":1,"url":"https://app.galxe.com/","steps":["Set GALXE_ACCESS_TOKEN in .env","Run /auto_quest — bot queries GraphQL API","Bot finds quests where you are already eligible","Bot auto-claims all available rewards","No human interaction needed"],"requires":["Galxe access token","Completed quests"],"cost":0},
    {"id":"GL2","title":"Galxe — Daily quest scan and complete","platform":"Galxe","category":"intermediate","reward":3.0,"reward_token":"Points (varies daily)","difficulty":"easy","estimated_minutes":1,"url":"https://app.galxe.com/","steps":["Run /auto_quest — bot scans all active spaces","Bot filters for on-chain-action quests","Bot executes required on-chain transactions","Bot verifies completion via GraphQL eligibility check","Bot claims available rewards"],"requires":["Galxe access token","EVM wallet"],"cost":0},
    {"id":"ZB1","title":"Zerion bridge Sepolia to Monad","platform":"Zerion","category":"intermediate","reward":0.0,"reward_token":"Monad airdrop eligibility","difficulty":"easy","estimated_minutes":2,"url":"https://api.zerion.io/v1/swap/quotes/","steps":["Fund Sepolia wallet with testnet ETH (free from faucet)","Set ZERION_API_KEY in .env","Run /auto_quest — bot gets Sepolia to Monad bridge quote","Bot signs and broadcasts the bridge transaction","Bot receives MON on destination chain"],"requires":["Zerion API key","Sepolia ETH (free)"],"cost":0},
    {"id":"ZB2","title":"Zerion bridge Ethereum to Berachain","platform":"Zerion","category":"intermediate","reward":0.0,"reward_token":"Berachain airdrop eligibility","difficulty":"easy","estimated_minutes":2,"url":"https://api.zerion.io/v1/swap/quotes/","steps":["Fund Ethereum wallet with small amount of ETH","Set ZERION_API_KEY in .env","Run /auto_quest — bot gets Ethereum to Berachain quote","Bot signs and broadcasts bridge transaction","Bot receives BERA on Berachain"],"requires":["Zerion API key","Mainnet ETH"],"cost":2.0},
    {"id":"MS1","title":"Multi-chain 24h auto-farming cycle","platform":"Multi-chain","category":"advanced","reward":0.0,"reward_token":"3x airdrops + Galxe points","difficulty":"medium","estimated_minutes":10,"url":"https://t.me/yieldabot","steps":["Run /auto_quest — bot begins 24h cycle","Phase 1 Claim faucets on all 3 testnets","Phase 2 Execute swaps stakes deploys on all 3 chains","Phase 3 Scan Galxe for completable quests","Phase 4 Bridge via Zerion across chain pairs","Phase 5 Log all tx hashes for airdrop proof"],"requires":["EVM wallet","Faucet tokens","Galxe + Zerion keys"],"cost":0},
    {"id":"SQ1","title":"Somnia Quest Portal auto daily","platform":"Somnia","category":"intermediate","reward":0.0,"reward_token":"Somnia quest points","difficulty":"easy","estimated_minutes":2,"url":"https://quest.somnia.network/","steps":["Connect wallet to quest.somnia.network","Run /auto_quest — bot stakes STT via staking dashboard","Bot bridges via Stargate/Relay","Bot checks for new campaigns and leaderboard position"],"requires":["EVM wallet","Faucet STT (free)"],"cost":0},
    {"id":"BZ1","title":"Testnet bridge rotation","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"LayerZero + protocol airdrops","difficulty":"easy","estimated_minutes":3,"url":"https://t.me/yieldabot","steps":["Run /auto_quest — bot executes bridge transactions","Routes Monad BSC testnet Berachain Sepolia Somnia Relay","Each bridge = unique on-chain footprint","LayerZero retroactively rewards active bridgers"],"requires":["EVM wallet","Small gas on source chain"],"cost":0},
    {"id":"SD1","title":"Deploy contract to Solana devnet","platform":"Solana","category":"intermediate","reward":0.0,"reward_token":"Devnet practice + potential","difficulty":"medium","estimated_minutes":3,"url":"https://solfaucet.com/","steps":["Generate Solana wallet /solana_wallet","Get devnet SOL from solfaucet.com","Run /auto_quest — bot deploys minimal Solana program","Deploying contracts = high-quality testnet activity"],"requires":["Solana wallet","Devnet SOL (free)"],"cost":0},
    {"id":"GF1","title":"Faucet rotation + auto-fund wallets","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"Free testnet gas","difficulty":"easy","estimated_minutes":2,"url":"https://t.me/yieldabot","steps":["Bot checks balance across all 3 testnet wallets","If balance below threshold claims from available faucet","Rotates through 13+ faucets across Monad Berachain Somnia","Ensures wallets never run out of gas for auto-transactions"],"requires":["EVM wallets","No capital"],"cost":0}

]


class QuestTracker:
    """Track user quest completion and accumulated earnings."""

    def __init__(self, user_id: int):
        self.user_id = str(user_id)

    def _load_completed(self) -> Dict[str, Any]:
        try:
            with open(COMPLETED_FILE, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"users": {}}
        return data

    def _save_completed(self, data: Dict[str, Any]) -> None:
        with open(COMPLETED_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _load_earnings(self) -> Dict[str, Any]:
        try:
            with open(EARNINGS_FILE, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"users": {}}
        return data

    def _save_earnings(self, data: Dict[str, Any]) -> None:
        with open(EARNINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get_quests(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filter quests by category. None returns all."""
        completed = self._load_completed()
        user_completed = set(completed.get("users", {}).get(self.user_id, []))
        result = []
        for q in QUEST_CATALOG:
            if category and q["category"] != category:
                continue
            entry = dict(q)
            entry["completed"] = q["id"] in user_completed
            result.append(entry)
        return result

    def complete_quest(self, quest_id: str) -> Dict[str, Any]:
        """Mark a quest as completed and add its reward to earnings."""
        quest = next((q for q in QUEST_CATALOG if q["id"] == quest_id), None)
        if quest is None:
            return {"ok": False, "error": "Quest not found."}

        completed = self._load_completed()
        users = completed.setdefault("users", {})
        user_list = users.get(self.user_id, [])
        if quest_id in user_list:
            return {"ok": False, "error": "Quest already completed."}

        user_list.append(quest_id)
        users[self.user_id] = user_list
        self._save_completed(completed)

        earnings = self._load_earnings()
        eu = earnings.setdefault("users", {}).setdefault(self.user_id, {"total_usd": 0.0, "by_token": {}, "quests": []})
        eu["total_usd"] += quest["reward"]
        token = quest["reward_token"]
        eu["by_token"][token] = eu["by_token"].get(token, 0.0) + quest["reward"]
        eu["quests"].append({
            "id": quest_id,
            "title": quest["title"],
            "reward": quest["reward"],
            "token": token,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_earnings(earnings)

        return {
            "ok": True,
            "quest": quest["title"],
            "reward": quest["reward"],
            "token": quest["reward_token"],
            "total_earned": eu["total_usd"],
        }

    def get_earnings(self) -> Dict[str, Any]:
        """Return the user's accumulated earnings."""
        earnings = self._load_earnings()
        eu = earnings.get("users", {}).get(self.user_id, {})
        if not eu:
            return {"total_usd": 0.0, "by_token": {}, "quests_completed": 0, "quests": []}
        return {
            "total_usd": eu.get("total_usd", 0.0),
            "by_token": eu.get("by_token", {}),
            "quests_completed": len(eu.get("quests", [])),
            "quests": eu.get("quests", []),
        }