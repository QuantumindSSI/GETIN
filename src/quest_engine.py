import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

COMPLETED_FILE = "completed_quests.json"
EARNINGS_FILE = "earnings.json"

# Curated quest catalog — all values are SIMULATED for demo purposes only.
# No real tokens are transferred. No real platforms are contacted.
# These are tutorial descriptions of real platforms; completions are
# tracked locally for demonstration purposes.
# IMPORTANT: Rewards shown are TUTORIAL ILLUSTRATIONS.
# Actual rewards depend on platform acceptance and are never guaranteed.

QUEST_CATALOG: List[Dict[str, Any]] = [
    # --- BEGINNER: zero capital, no wallet needed ---
    {
        "id": "S1",
        "title": "Superteam Earn — First Bounty",
        "platform": "Superteam",
        "category": "beginner",
        "reward": 0.0,
        "reward_token": "SIMULATED — Actual rewards depend on platform acceptance",
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
        "reward": 0.0,
        "reward_token": "SIMULATED — Actual rewards depend on platform acceptance",
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
        "reward": 0.0,
        "reward_token": "SIMULATED — Actual rewards depend on campaign",
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
        "reward": 0.0,
        "reward_token": "SIMULATED — IF bounty accepted by platform",
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
        "reward": 0.0,
        "reward_token": "SIMULATED — Depends on platform streak rules",
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
        "reward_token": "SPECULATIVE — Potential airdrop only (no guaranteed value)",
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
        "reward_token": "SPECULATIVE — Potential airdrop only (no guaranteed value)",
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
        "reward": 0.0,
        "reward_token": "SIMULATED — IF content accepted by platform",
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
        "reward": 0.0,
        "reward_token": "SIMULATED — Depends on platform sprint rules",
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
        "reward_token": "SPECULATIVE — Airdrops are never guaranteed",
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
    # ---- Demo activity tracker (completions are local only, no real value) ----
    {"id":"GQ1","title":"Galxe — Scan Solana Campaigns (demo)","platform":"Galxe","category":"intermediate","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":1,"url":"https://app.galxe.com/","steps":["This is a DEMO quest. No real API integration.","No tokens are transferred. No platforms are contacted.","Tracked locally for demonstration purposes."],"requires":["None — demo only"],"cost":0},
    {"id":"MO1","title":"Monad Testnet — Practice swap+stake (demo)","platform":"Monad Testnet","category":"advanced","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"medium","estimated_minutes":5,"url":"https://testnet.monad.xyz/","steps":["This is a DEMO quest. No real transactions are automated.","The auto-farmer uses testnet RPCs for testing only.","Actual airdrops are never guaranteed."],"requires":["EVM wallet","Faucet MON (free)"],"cost":0},
    {"id":"BR1","title":"Berachain — Practice swap+stake (demo)","platform":"Berachain Testnet","category":"advanced","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"medium","estimated_minutes":5,"url":"https://bartio.bex.berachain.com/","steps":["This is a DEMO quest. No real transactions are automated.","The auto-farmer uses dummy contract addresses.","Actual airdrops are never guaranteed."],"requires":["EVM wallet","Faucet BERA (free)"],"cost":0},
    {"id":"SM1","title":"Somnia — Practice stake+deploy (demo)","platform":"Somnia Testnet","category":"advanced","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":5,"url":"https://testnet.somnia.network/","steps":["This is a DEMO quest. No real transactions are automated.","The auto-farmer uses dummy contract addresses.","Actual airdrops are never guaranteed."],"requires":["EVM wallet","Faucet STT (free)"],"cost":0},
    {"id":"AQ1","title":"Faucet rotation check (demo)","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":2,"url":"https://t.me/yieldabot","steps":["This is a DEMO quest.","Faucets require manual CAPTCHA solving.","No automated claiming is available."],"requires":["EVM wallet","No capital"],"cost":0},
    {"id":"CV1","title":"Deploy contract practice (demo)","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":2,"url":"https://t.me/yieldabot","steps":["This is a DEMO quest.","The deploy function uses compiled bytecode.","Actual deployment may fail with dummy addresses."],"requires":["EVM wallet","Faucet tokens (free)"],"cost":0},
    {"id":"GR1","title":"Grass — Bandwidth sharing node (manual setup)","platform":"Grass","category":"advanced","reward":0.0,"reward_token":"SIMULATED — Depends on Grass Foundation rewards","difficulty":"easy","estimated_minutes":1,"url":"https://www.grassfoundation.io/","steps":["Install the Grass desktop app or browser extension","Run it in the background 24/7","Grass Foundation may reward bandwidth contributors","Fully passive — no clicks after setup"],"requires":["Desktop or VPS","Internet connection"],"cost":0},
    {"id":"TP1","title":"Tea Protocol — Register OSS repo (manual)","platform":"Tea Protocol","category":"advanced","reward":0.0,"reward_token":"SIMULATED — Depends on Tea Protocol rewards","difficulty":"medium","estimated_minutes":5,"url":"https://app.tea.xyz/","steps":["Go to app.tea.xyz and connect wallet","Register your open-source GitHub repo","Tea Protocol auto-calculates your teaRank","Stake TEA tokens on your project for rewards","Higher ecosystem impact = higher rewards"],"requires":["GitHub repo","Crypto wallet"],"cost":0},
    {"id":"TP2","title":"Tea Protocol — Staking (manual)","platform":"Tea Protocol","category":"advanced","reward":0.0,"reward_token":"SIMULATED — Depends on staking yield","difficulty":"easy","estimated_minutes":2,"url":"https://app.tea.xyz/","steps":["Acquire TEA tokens (earned from TP1 or bought)","Go to app.tea.xyz/staking","Stake TEA on high-ranked OSS projects","Earn continuous staking rewards","Requires manual smart contract interaction"],"requires":["TEA tokens","Crypto wallet"],"cost":20.0},
    {"id":"GL1","title":"Galxe — Account review (demo)","platform":"Galxe","category":"intermediate","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":1,"url":"https://app.galxe.com/","steps":["This is a DEMO quest. No API integration exists.","Galxe GraphQL API requires access tokens.","No automatic claiming is implemented."],"requires":["Galxe access token","Completed quests"],"cost":0},
    {"id":"GL2","title":"Galxe — Campaign browser (demo)","platform":"Galxe","category":"intermediate","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":1,"url":"https://app.galxe.com/","steps":["This is a DEMO quest.","The Galxe client can READ campaign data only.","No mutations (create/claim) are implemented."],"requires":["Galxe access token","EVM wallet"],"cost":0},
    {"id":"ZB1","title":"Zerion — Bridge demo (manual only)","platform":"Zerion","category":"intermediate","reward":0.0,"reward_token":"SPECULATIVE — Airdrop is never guaranteed","difficulty":"easy","estimated_minutes":2,"url":"https://api.zerion.io/v1/swap/quotes/","steps":["Fund Sepolia wallet with testnet ETH (free from faucet)","Zerion API key required for quotes only","Actual bridging requires manual transaction signing","No automated bridge execution is available"],"requires":["Zerion API key","Sepolia ETH (free)"],"cost":0},
    {"id":"ZB2","title":"Zerion bridge demo (manual only)","platform":"Zerion","category":"intermediate","reward":0.0,"reward_token":"SPECULATIVE — Airdrop is never guaranteed","difficulty":"easy","estimated_minutes":2,"url":"https://api.zerion.io/v1/swap/quotes/","steps":["Fund Ethereum wallet with small amount of ETH","Zerion API key required for quotes only","Actual bridging requires manual transaction signing","No automated bridge execution is available"],"requires":["Zerion API key","Mainnet ETH"],"cost":2.0},
    {"id":"MS1","title":"Multi-chain demo cycle","platform":"Multi-chain","category":"advanced","reward":0.0,"reward_token":"SPECULATIVE — Airdrops are never guaranteed","difficulty":"medium","estimated_minutes":10,"url":"https://t.me/yieldabot","steps":["This is a DEMO cycle. No real automation is performed.","All quest completions are local JSON entries only.","Real on-chain activity MUST be done manually."],"requires":["EVM wallet","Faucet tokens"],"cost":0},
    {"id":"SQ1","title":"Somnia Quest Portal (demo)","platform":"Somnia","category":"intermediate","reward":0.0,"reward_token":"SPECULATIVE — Quest points only","difficulty":"easy","estimated_minutes":2,"url":"https://quest.somnia.network/","steps":["Connect wallet to quest.somnia.network manually","Quest completions are tracked locally only","No automatic quest completion is available"],"requires":["EVM wallet","Faucet STT (free)"],"cost":0},
    {"id":"BZ1","title":"Testnet bridge demo","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"SPECULATIVE — Airdrops are never guaranteed","difficulty":"easy","estimated_minutes":3,"url":"https://t.me/yieldabot","steps":["This is a DEMO quest.","Bridging requires manual wallet interaction.","No automated bridge execution is available."],"requires":["EVM wallet","Small gas on source chain"],"cost":0},
    {"id":"SD1","title":"Solana devnet deploy (demo)","platform":"Solana","category":"intermediate","reward":0.0,"reward_token":"DEMO — Devnet practice only, no mainnet value","difficulty":"medium","estimated_minutes":3,"url":"https://solfaucet.com/","steps":["Generate Solana wallet /solana_wallet","Get devnet SOL from solfaucet.com","Manual deployment only — no automatic Solana program deployment","Devnet SOL has no mainnet value"],"requires":["Solana wallet","Devnet SOL (free)"],"cost":0},
    {"id":"GF1","title":"Faucet rotation (demo)","platform":"Multi-chain","category":"intermediate","reward":0.0,"reward_token":"DEMO — Simulated tracking only","difficulty":"easy","estimated_minutes":2,"url":"https://t.me/yieldabot","steps":["This is a DEMO quest.","Faucets require manual CAPTCHA solving.","No automated claiming is available."],"requires":["EVM wallets","No capital"],"cost":0},
    {"id":"CW1","title":"Superteam — Write a tutorial blog post (demo)","platform":"Superteam","category":"intermediate","reward":0.0,"reward_token":"SIMULATED — IF submission accepted by Superteam","difficulty":"medium","estimated_minutes":2,"url":"https://earn.superteam.fun/","steps":["Run /write tutorial TOPIC","The AI generates TEMPLATE content — you MUST review and customize","Generated content is generic and needs significant human editing","Submit to Superteam Content category ONLY after rewriting","Actual rewards depend entirely on Superteam acceptance"],"requires":["Superteam account","Solana wallet"],"cost":0},
    {"id":"CW2","title":"Superteam — Write a Twitter thread (demo)","platform":"Superteam/Twitter","category":"beginner","reward":0.0,"reward_token":"SIMULATED — IF submission accepted by Superteam","difficulty":"easy","estimated_minutes":1,"url":"https://earn.superteam.fun/","steps":["Run /write thread TOPIC","The AI generates TEMPLATE content — you MUST review and customize","Post to Twitter ONLY after substantial human editing","Submit URL to Superteam bounty","Actual rewards depend entirely on Superteam acceptance"],"requires":["Twitter account","Superteam account","Twitter API keys"],"cost":0},
    {"id":"CW3","title":"Layer3 — Write a crypto guide (demo)","platform":"Layer3","category":"intermediate","reward":0.0,"reward_token":"SIMULATED — IF submission accepted by Layer3","difficulty":"easy","estimated_minutes":2,"url":"https://app.layer3.xyz/quests","steps":["Find a Layer3 writing quest manually","Run /write tutorial TOPIC for DRAFT content only","Must substantially rewrite before submission","Submit through Layer3 interface manually"],"requires":["Layer3 account"],"cost":0},
    {"id":"CW4","title":"GitHub Docs — Documentation contribution (demo)","platform":"GitHub/GitBook/Tea Protocol","category":"advanced","reward":0.0,"reward_token":"SIMULATED — Depends on Gitcoin/Tea Protocol matching","difficulty":"medium","estimated_minutes":2,"url":"https://app.tea.xyz/","steps":["Find open-source project needing docs","Run /write docs PROJECT PAGETITLE for DRAFT only","The AI generates FABRICATED SDK code — verify against real API","Submit as GitHub PR only after accuracy verification","Register on Tea Protocol manually"],"requires":["GitHub account","Project knowledge"],"cost":0},
    {"id":"CW5","title":"Bug bounty — Security research (HUMAN-REQUIRED)","platform":"Immunefi/Superteam","category":"advanced","reward":0.0,"reward_token":"SIMULATED — Requires REAL vulnerability discovery (AI CANNOT do this)","difficulty":"hard","estimated_minutes":3,"url":"https://immunefi.com/bug-bounty/","steps":["WARNING: AI-generated bug reports are FABRICATED templates only","They describe NOVEL vulnerabilities that DO NOT EXIST","Submitting fabricated reports to Immunefi is a terms violation","You risk permanent platform blacklisting","Real bug bounty work requires: manual code audit, fuzzing, and verification","The AI report template is a FORMATTING EXAMPLE only — never submit as-is"],"requires":["Immunefi account","Technical skills","Mandatory: manual vulnerability verification"],"cost":0},
    {"id":"CW6","title":"Daily crypto news summary (demo)","platform":"Layer3/Galxe","category":"beginner","reward":0.0,"reward_token":"SIMULATED — IF submission accepted","difficulty":"easy","estimated_minutes":1,"url":"https://app.layer3.xyz/quests","steps":["Run /write tutorial CRYPTO TOPIC","AI generates a DRAFT summary only","Must verify facts, add current data, and rewrite","Submit through quest platform manually"],"requires":["Platform account"],"cost":0},
    {"id":"CW7","title":"Write a project review (demo)","platform":"Superteam","category":"advanced","reward":0.0,"reward_token":"SIMULATED — IF submission accepted","difficulty":"medium","estimated_minutes":2,"url":"https://earn.superteam.fun/","steps":["Run /write tutorial PROJECT review","AI generates a DRAFT only — requires substantial human editing","Customize with real personal experience","Submit to Superteam only after significant rewriting"],"requires":["Superteam account","Solana wallet"],"cost":0},
    {"id":"CW8","title":"Quiz study helper (no answers provided)","platform":"Multi-platform","category":"beginner","reward":0.0,"reward_token":"SIMULATED — Educational tool only","difficulty":"easy","estimated_minutes":1,"url":"https://app.layer3.xyz/quests","steps":["This generates a STUDY GUIDE with resource links only","No actual quiz answers are provided","Use the guide to research the topic yourself","Submit your own work on the platform","Do NOT submit AI-generated content to bounty platforms"],"requires":["Platform account"],"cost":0}
]


class QuestTracker:
    """
    Track user quest completion and accumulated earnings.
    IMPORTANT: All values are SIMULATED for local demonstration only.
    No real tokens are transferred. No platforms are contacted automatically.
    Completions are LOCAL JSON entries — they do not represent real earnings.
    """

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
        """
        Mark a quest as completed in LOCAL tracking only.
        WARNING: This is a DEMO feature. No real platforms are contacted.
        No real tokens are earned. Completions are simulated for UX testing.
        """
        quest = next((q for q in QUEST_CATALOG if q["id"] == quest_id), None)
        if quest is None:
            return {"ok": False, "error": "Quest not found."}

        completed = self._load_completed()
        users = completed.setdefault("users", {})
        user_list = users.get(self.user_id, [])
        if quest_id in user_list:
            return {"ok": False, "error": "Quest already tracked."}

        user_list.append(quest_id)
        users[self.user_id] = user_list
        self._save_completed(completed)

        earnings = self._load_earnings()
        eu = earnings.setdefault("users", {}).setdefault(
            self.user_id, {"total_usd": 0.0, "by_token": {}, "quests": []}
        )
        eu["total_usd"] += 0.0
        token = "SIMULATED — No real value"
        eu["by_token"][token] = eu["by_token"].get(token, 0.0) + 0.0
        eu["quests"].append({
            "id": quest_id,
            "title": quest["title"],
            "reward": 0.0,
            "token": token,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "note": "LOCAL TRACKING ONLY — No real tokens earned.",
        })
        self._save_earnings(earnings)

        return {
            "ok": True,
            "quest": quest["title"],
            "reward": 0.0,
            "token": "SIMULATED — No real value is earned by /complete",
            "total_earned": eu["total_usd"],
            "warning": "Quest completions are local tracking only. No real platforms are contacted. No tokens are earned.",
        }

    def get_earnings(self) -> Dict[str, Any]:
        earnings = self._load_earnings()
        eu = earnings.get("users", {}).get(self.user_id, {})
        if not eu:
            return {
                "total_usd": 0.0,
                "by_token": {},
                "quests_completed": 0,
                "quests": [],
                "warning": "Quest completions are local tracking only. Actual earnings require manual completion on each platform.",
            }
        return {
            "total_usd": 0.0,
            "by_token": {"NOTE: All quest rewards are simulated. No real tokens.": 0.0},
            "quests_completed": len(eu.get("quests", [])),
            "quests": eu.get("quests", []),
            "warning": "These are LOCAL tracking entries only. No real platforms were contacted. No tokens were earned.",
        }