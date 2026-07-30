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