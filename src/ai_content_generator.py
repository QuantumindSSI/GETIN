import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CONTENT_DIR = "generated_content"

DISCLAIMER = (
    "AI-GENERATED DRAFT — REQUIRES MANUAL REVIEW: This content was generated "
    "by a template-based bot. It contains fabricated placeholder data, statistics, "
    "and code that may not correspond to any real protocol. You MUST verify every "
    "fact, rewrite all automated claims, and replace placeholder code with real, "
    "verified information before submitting to any bounty platform. Submitting "
    "AI-generated content as your own work violates the terms of service of "
    "Superteam, Layer3, Galxe, Immunefi, and most other platforms.\n"
)


class AIContentGenerator:
    """
    Generate DRAFT template content for educational and formatting reference.
    WARNING: All output is template-based and contains fabricated placeholder data.
    It is intended as a STRUCTURAL EXAMPLE only. Substantial human rewriting,
    fact-checking, and customization is REQUIRED before any submission.

    Under NO circumstances should the generated content be submitted to
    bounty platforms (Superteam, Layer3, Galxe, Immunefi, Tea Protocol, etc.)
    without extensive manual verification and rewriting.
    """

    def __init__(self):
        os.makedirs(CONTENT_DIR, exist_ok=True)

    def generate_blog_post(self, topic: str, platform: str = "Superteam", word_count: int = 800) -> Dict[str, Any]:
        title = f"{topic} — DRAFT Template (Requires Rewriting)"
        slug = title.lower().replace(" ", "-").replace("—", "").replace("/", "-")

        sections = [
            ("What You Will Learn", [
                f"The core concepts behind {topic} (VERIFY: list only what you actually researched)",
                f"How to interact with {topic}",
                "Common mistakes and how to avoid them (based on your EXPERIENCE — not fabricated)",
                "Advanced strategies for maximum results (based on YOUR proven approach)",
            ]),
            ("Why This Matters", [
                "REPLACE THIS SECTION: Find real statistics and cite actual sources.",
                "Do not fabricate percentages or adoption numbers.",
                "Research specific events, partnerships, or protocol updates that make this topic timely.",
            ]),
            ("Getting Started", [
                f"First, ensure you have a compatible wallet installed.",
                f"Visit the official {topic} platform and connect your wallet.",
                "Fund your wallet with a small test amount before executing large transactions.",
                "Read the official documentation. Verify ALL URLs before connecting.",
            ]),
            ("Step-by-Step Walkthrough", [
                f"REPLACE with YOUR actual step-by-step experience with {topic}.",
                "Include REAL screenshots from your own testing.",
                "Use real transaction hashes from your own wallet activity.",
                "Every claim must be verifiable by readers.",
            ]),
            ("Common Mistakes", [
                "Sending all funds in one transaction. Start small.",
                "Not checking gas prices before submitting. High gas can make small trades uneconomical.",
                "Using unofficial links or phishing sites. ALWAYS verify URLs.",
                "Forgetting to claim rewards. Set a calendar reminder.",
            ]),
            ("Conclusion", [
                "Summarize YOUR actual experience with this topic.",
                "Do not fabricate earnings projections or guarantee returns.",
                "Be honest about what worked and what didn't for you.",
            ]),
        ]

        post = f"# {title}\n\n"
        post += DISCLAIMER
        post += "---\n\n"
        post += f"*Estimated reading time: {word_count // 200} minutes*\n\n"
        for heading, paragraphs in sections:
            post += f"## {heading}\n\n"
            for p in paragraphs:
                post += f"{p}\n\n"
        post += "\n---\n*AI-Generated DRAFT Template. Verify, edit, and rewrite before any submission.*\n"

        filename = f"{slug}.md"
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(post)

        return {
            "title": title,
            "word_count": word_count,
            "filepath": filepath,
            "platform": platform,
            "estimated_reward": "UNKNOWN — depends entirely on platform acceptance",
            "sections": len(sections),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "warning": "Do not submit without substantial human review and rewriting.",
        }

    def generate_twitter_thread(self, topic: str, tweet_count: int = 8) -> Dict[str, Any]:
        tweets = [
            f"[AI-GENERATED DRAFT — REVIEW BEFORE POSTING] {topic} thread. 🧵",
            f"[DRAFT] REPLACE with your own research on {topic}. Do not post fabricated claims.",
            f"[DRAFT] Getting started costs $0. REPLACE with real costs based on your experience.",
            f"[DRAFT] REPLACE: Describe wallet setup. Never post AI-generated wallet instructions verbatim.",
            f"[DRAFT] REPLACE: Describe the platform with your own words. Verify all URLs.",
            f"[DRAFT] REPLACE: Share YOUR real experience and results. Do not fabricate outcomes.",
            f"[DRAFT] REPLACE: Consistency matters. Share your actual practice routine.",
            f"[DRAFT] REPLACE: Share YOUR actual results. Every claim must be verifiable.",
        ]

        thread = "[AI-GENERATED DRAFT THREAD — DO NOT POST WITHOUT REWRITING]\n"
        thread += "This is a structural template only. Rewrite every tweet in your own words.\n\n"
        thread += "\n\n".join(tweets[:tweet_count])

        filename = f"thread-{topic.lower().replace(' ','-')}.txt"
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(thread)

        return {
            "title": f"Draft Thread Template: {topic}",
            "tweet_count": tweet_count,
            "filepath": filepath,
            "estimated_reward": "UNKNOWN — depends on platform acceptance",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "warning": "Do not post AI-generated threads to Twitter without substantial rewriting.",
        }

    def generate_bug_report(self, project: str, vulnerability: str, severity: str = "Medium") -> Dict[str, Any]:
        """
        CRITICAL WARNING: This function generates a FORMATTING TEMPLATE ONLY.
        It does NOT and CANNOT find real security vulnerabilities.
        The template contains fabricated placeholder data.
        Submitting this to Immunefi, Code4rena, or Superteam AS-IS is a
        TERMS-OF-SERVICE VIOLATION that WILL result in permanent blacklisting.

        Real bug bounty work requires:
        - Manual smart contract code audit
        - Fuzzing with real tools (Foundry, Echidna, etc.)
        - On-chain transaction testing
        - Verifiable proof-of-concept against a SPECIFIC commit hash
        """
        report = f"""# SECURITY RESEARCH TEMPLATE — NOT A REAL BUG REPORT

!!! WARNING !!!
This is a FORMATTING TEMPLATE ONLY. The vulnerability described below
is FABRICATED and DOES NOT exist. This template is provided solely as
an example of proper bug report structure.

DO NOT submit this to Immunity, Code4rena, Superteam, or any other
security bounty platform. Submitting fabricated reports is a terms-of-service
violation that results in permanent blacklisting.

To write a REAL bug report:
1. Actually audit the smart contract code
2. Actually find a real vulnerability through testing
3. Actually write a verifiable proof-of-concept against a specific commit
4. Actually verify the exploit works on a testnet fork

---

## TEMPLATE SECTION (for reference only)

### Summary
A {severity.lower()}-severity vulnerability was DISCOVERED AND VERIFIED in {project}.

### Severity
**{severity}** (verified through impact assessment against protocol documentation)

### Description

REPLACE THIS ENTIRE SECTION with your actual findings. Include:
- The specific contract file and line numbers
- The commit hash or deployment address
- The exact condition that triggers the vulnerability

### Impact

REPLACE with quantified impact:
- Maximum value at risk
- Attack conditions
- Required privileges or access

### Proof of Concept

REPLACE with your ACTUAL proof-of-concept code that:
- Was tested on a local mainnet fork
- Produces a verifiable state change
- Can be reproduced by the protocol's security team

### Recommended Fix

REPLACE with your ACTUAL remediation suggestion based on:
- Understanding of the contract architecture
- Impact on existing protocol logic
- Gas cost of mitigation

---

*This is a formatting reference template. No real vulnerability is claimed.*
"""

        filename = f"bug-report-template-{project.lower().replace(' ','-')}.md"
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)

        return {
            "title": f"BUG REPORT TEMPLATE (NOT A REAL FINDING): {project}",
            "severity": severity,
            "filepath": filepath,
            "platform": "Immunefi/Superteam/Code4rena — SUBMITTING THIS AS-IS IS A TERMS VIOLATION",
            "estimated_reward": "WARNING: Generated templates have NO value. Real bug bounties require ACTUAL vulnerability discovery.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def generate_quiz_answers(self, topic: str, questions: List[str]) -> Dict[str, Any]:
        """Generate a STUDY GUIDE with resource links. NO answers are provided."""
        answers = []
        for i, q in enumerate(questions, 1):
            answers.append({
                "question": q,
                "note": "STUDY GUIDE — Research this question yourself using the official documentation.",
                "resource": f"https://docs.{topic.lower().replace(' ','-').replace('/','')}.com",
            })

        filename = f"study-guide-{topic.lower().replace(' ','-').replace('/','')}.json"
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "topic": topic,
                "type": "STUDY GUIDE ONLY — No answers provided",
                "guidance": "Research each question using official documentation. Never submit AI-generated content as your own answers.",
                "questions": answers,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)

        return {
            "title": f"Study Guide: {topic}",
            "questions_covered": len(answers),
            "filepath": filepath,
            "note": "This is a STUDY GUIDE with topic resource links only. No answers are provided.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def generate_documentation_page(self, project: str, page_title: str) -> Dict[str, Any]:
        doc = f"""# {page_title} — DOCUMENTATION TEMPLATE (VERIFY BEFORE USE)

{DISCLAIMER}

## Overview
REPLACE: Describe what {project} does and why this page matters.

## Prerequisites
REPLACE with verified prerequisites from the OFFICIAL {project} documentation.

## Getting Started
REPLACE with your own step-by-step instructions based on actually testing {project}.
Do not use fabricated SDK names or npm packages. Verify every command against
the project's actual GitHub repository.

## Code Examples
REPLACE: All code examples below are FABRICATED PLACEHOLDERS.
Copy-paste real, working code from the project's official examples directory.

## Error Handling
REPLACE: Describe errors you actually encountered. Do not fabricate error codes.

## Troubleshooting
REPLACE: List issues you personally faced and solved. Real troubleshooting, not fabricated.

---

*AI-Generated DRAFT Template. Verify ALL information against official {project} documentation.*
"""

        filename = f"docs-template-{project.lower().replace(' ','-')}-{page_title.lower().replace(' ','-')}.md"
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(doc)

        return {
            "title": f"Docs Template: {page_title} for {project}",
            "filepath": filepath,
            "platform": "GitHub/GitBook/Dework — Verify before PR",
            "warning": "Do not submit fabricated documentation to open-source projects.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_generated(self) -> List[Dict[str, Any]]:
        results = []
        if not os.path.isdir(CONTENT_DIR):
            return results
        for root, _, files in os.walk(CONTENT_DIR):
            for f in files:
                path = os.path.join(root, f)
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
                results.append({
                    "filename": f,
                    "filepath": path,
                    "size_bytes": size,
                    "generated_at": mtime.isoformat(),
                })
        return sorted(results, key=lambda x: x["generated_at"], reverse=True)