# Manual Trading Signals via Discord

This feature allows authorized Discord users to send manual BUY/SELL commands to the trading bot, overriding the automated RSI strategy when needed.

## Setup

### 1. Configure Authorized Users

Add Discord user IDs to your `.env` file:

```bash
# Comma-separated list of Discord user IDs
DISCORD_AUTHORIZED_USERS=123456789012345678,987654321098765432
```

To find your Discord user ID:
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click your username and select "Copy User ID"

### 2. How It Works

The bot checks for manual signals at the beginning of each trading cycle (every 30 seconds). Manual signals take priority over automated RSI signals.

## Sending Manual Commands

There are two ways to send manual commands:

### Method 1: Direct Signal Injection (Testing)

Use the provided test script:

```bash
python test_manual_signal.py
```

Follow the prompts to:
1. Enter command (BUY or SELL)
2. Enter your Discord user ID
3. Enter your Discord username

### Method 2: Discord Webhook Integration (Production)

You can set up a Discord bot or webhook to send commands to the trading bot. The bot expects a JSON payload with:

```json
{
  "user_id": "123456789012345678",
  "username": "YourDiscordName",
  "content": "BUY"
}
```

## Command Rules

### BUY Command
- Only executes if the bot has no current position
- Uses current market price
- Applies same position sizing and risk management as automated trades
- Checks fee profitability before execution

### SELL Command
- Only executes if the bot has an open position
- Closes the entire position
- Calculates and reports PnL

## Feedback

The bot sends Discord notifications for:
- ✅ Successful command execution
- ❌ Failed commands (with reason)
- Position already exists (for BUY)
- No position to close (for SELL)

## Security

- Only authorized Discord user IDs can send commands
- Commands are validated before execution
- All manual trades are logged
- Manual signals respect the bot's risk management rules

## Example Flow

1. User sends "BUY" command
2. Bot receives command in next cycle (max 30 seconds)
3. Bot validates:
   - User is authorized
   - No existing position
   - Sufficient balance
   - Fees are profitable
4. Bot executes market buy order
5. Bot sends Discord notification with result

## Monitoring

Manual signal statistics are included in the bot's status updates:
- Number of pending signals
- Number of processed signals
- Last signal timestamp

## Important Notes

- Manual signals override automated RSI signals for that cycle
- Stop loss still applies to manually opened positions
- All risk management rules remain active
- Manual trades are included in ROI calculations
- Bot continues automated trading after processing manual signals