#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_API="https://api.telegram.org/bot${BOT_TOKEN}"

echo "=== GETIN Bot Command Test Suite ==="

if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN not set."
    exit 1
fi

send_cmd() {
    local chat_id="$1"
    local text="$2"
    curl -s -X POST "${TELEGRAM_API}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\": \"${chat_id}\", \"text\": \"${text}\", \"parse_mode\": \"HTML\"}" \
        -o /dev/null -w "  HTTP %{http_code}"
}

echo ""
echo "Chat ID: ${TELEGRAM_OWNER_ID:-not set}"
echo ""

# Wait for bot to be ready
sleep 2

echo "1. /start"
send_cmd "${TELEGRAM_OWNER_ID}" "/start"
echo ""

echo "2. /help"
send_cmd "${TELEGRAM_OWNER_ID}" "/help"
echo ""

echo "3. /yield"
send_cmd "${TELEGRAM_OWNER_ID}" "/yield"
echo ""

echo "4. /market"
send_cmd "${TELEGRAM_OWNER_ID}" "/market"
echo ""

echo "5. /prices BTC ETH SOL"
send_cmd "${TELEGRAM_OWNER_ID}" "/prices BTC ETH SOL"
echo ""

echo "6. /prices ADA DOGE"
send_cmd "${TELEGRAM_OWNER_ID}" "/prices ADA DOGE"
echo ""

echo "7. /activities"
send_cmd "${TELEGRAM_OWNER_ID}" "/activities"
echo ""

echo "8. /wallet (private only - skipped in group)"
echo "   Use /wallet and /solana_wallet in DM with the bot"
echo ""

echo "9. /upgrade"
send_cmd "${TELEGRAM_OWNER_ID}" "/upgrade"
echo ""

echo "10. /set_premium ${TELEGRAM_OWNER_ID}"
send_cmd "${TELEGRAM_OWNER_ID}" "/set_premium ${TELEGRAM_OWNER_ID}"
echo ""

echo "11. /subscribe"
send_cmd "${TELEGRAM_OWNER_ID}" "/subscribe"
echo ""

echo ""
echo "=== Test suite complete ==="
echo "Check your Telegram chat for bot responses."