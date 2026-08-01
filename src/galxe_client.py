import json
import os
import time
from typing import Any, Dict, List, Optional

import requests

GALXE_GQL = "https://graphigo-business.prd.galaxy.eco/query"
GALXE_ACCESS_TOKEN_ENV = "GALXE_ACCESS_TOKEN"


class GalxeClient:
    """
    Read-only Galxe GraphQL client for quest discovery and eligibility checks.

    WARNING: Galxe does NOT offer a documented public API. The GraphQL endpoint
    and Query field names are speculative — reverse-engineered from browser
    inspection and NOT confirmed against any official documentation. The
    'access-token' auth header is unverified against any real Galxe deployment.
    This client may not work with any actual Galxe service.
    """

    def __init__(self, access_token: Optional[str] = None):
        self.token = access_token or os.getenv(GALXE_ACCESS_TOKEN_ENV)
        if not self.token:
            raise ValueError("GALXE_ACCESS_TOKEN is missing. Get one from dashboard.galxe.com")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "access-token": self.token,
        })

    def _query(self, operation: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query against the Galxe API."""
        payload = {"query": operation, "variables": variables}
        resp = self.session.post(GALXE_GQL, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if "errors" in result:
            raise RuntimeError(f"Galxe GraphQL error: {result['errors']}")
        return result.get("data", {})

    def list_active_quests(self, space_id: str, limit: int = 20) -> List[Dict]:
        """Fetch active quests in a Galxe space."""
        op = """
        query ListQuests($input: ListQuestInput!) {
            quests(input: $input) {
                totalCount
                list {
                    id
                    name
                    type
                    status
                    participantsCount
                    loyaltyPoints
                }
            }
        }
        """
        data = self._query(op, {"input": {"spaceId": space_id, "status": "ACTIVE", "limit": limit}})
        return data.get("quests", {}).get("list", [])

    def check_eligibility(self, quest_id: str, address: str) -> Dict[str, Any]:
        """Check if a wallet is eligible to claim a quest reward."""
        op = """
        query CheckEligibility($questId: ID!, $address: String!) {
            quest(id: $questId) {
                id
                name
                status
                credentialGroups(address: $address) {
                    conditions { expression eligible }
                    rewards { expression eligible rewardType rewardCount }
                }
            }
        }
        """
        data = self._query(op, {"questId": quest_id, "address": address.lower()})
        return data.get("quest", {})

    def find_automatable_quests(self, space_id: str, address: str) -> List[Dict]:
        """Find quests where a wallet is already eligible AND has unclaimed rewards.
    NOTE: This method reads data from the Galxe GraphQL API only.
    It does NOT complete quests, claim rewards, or perform any write operations."""
        quests = self.list_active_quests(space_id)
        results = []
        for q in quests:
            qid = q.get("id")
            if not qid:
                continue
            try:
                detail = self.check_eligibility(qid, address)
                cgs = detail.get("credentialGroups", [])
                for cg in cgs:
                    conditions = cg.get("conditions", [])
                    rewards = cg.get("rewards", [])
                    all_eligible = all(c.get("eligible", False) for c in conditions)
                    any_reward_ready = any(r.get("eligible", False) for r in rewards)
                    if all_eligible and not any_reward_ready:
                        still_needed = [r for r in rewards if not r.get("eligible", False)]
                        results.append({
                            "quest_id": qid,
                            "name": q.get("name"),
                            "type": q.get("type"),
                            "points": q.get("loyaltyPoints", 0),
                            "missing_rewards": len(still_needed),
                            "conditions_met": all_eligible,
                        })
                time.sleep(0.2)
            except Exception:
                continue
        return results

    def search_quests_by_token(self, token_symbol: str = "USDC") -> List[Dict]:
        """Search for quests that reward a specific token."""
        op = """
        query Search($keyword: String!, $limit: Int) {
            quests(input: { keyword: $keyword, limit: $limit }) {
                list { id name type status loyaltyPoints }
            }
        }
        """
        try:
            data = self._query(op, {"keyword": token_symbol, "limit": 20})
            return data.get("quests", {}).get("list", [])
        except Exception:
            return []