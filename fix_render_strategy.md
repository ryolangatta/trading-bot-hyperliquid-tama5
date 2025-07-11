# Fix Render Strategy Configuration

The error "Unknown strategy: rsi_pengu" is occurring because the bot is being started with the wrong strategy name on Render.

## Issue
The bot is trying to use `rsi_pengu` strategy, but the correct strategy name is `stochastic_rsi_link`.

## Solution

### Option 1: Update Render Dashboard (Recommended)
1. Go to your Render dashboard at https://dashboard.render.com
2. Navigate to your `hyperliquid-trading-bot` service
3. Go to the "Settings" tab
4. Find the "Start Command" field
5. Change it from:
   ```
   python main.py --strategy rsi_pengu
   ```
   To:
   ```
   python main.py --strategy stochastic_rsi_link
   ```
6. Click "Save Changes"
7. The bot will automatically redeploy with the correct strategy

### Option 2: Use Environment Variable
1. In Render dashboard, go to "Environment" tab
2. Ensure `STRATEGY_NAME` is set to `stochastic_rsi_link`
3. Update the start command to:
   ```
   python main.py
   ```
   (This will use the default strategy from the code)

### Option 3: Redeploy from render.yaml
If you want to ensure the render.yaml configuration is used:
1. Commit all changes to git
2. Push to your repository
3. In Render dashboard, trigger a manual deploy
4. Ensure "Auto-Deploy" is enabled for future updates

## Verification
After making the change, check the logs to ensure the bot starts with:
- Strategy: stochastic_rsi_link
- Symbol: LINK

The bot should no longer show the "Unknown strategy: rsi_pengu" error.