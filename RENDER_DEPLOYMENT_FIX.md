# Render Deployment Fix Guide

## Issues Fixed

1. **File Path Error**: `python: can't open file '/opt/render/project/src/main.py'`
   - **Cause**: The `rootDirectory` setting in render.yaml was causing Render to look for files in the wrong location
   - **Solution**: Removed `rootDirectory` and updated paths to use `hyperliquid_bot/main.py`

2. **Strategy Name Error**: `Unknown strategy: rsi_pengu`
   - **Cause**: Old strategy name was being used
   - **Solution**: Updated to use `stochastic_rsi_link`

## Updated Configuration

The render.yaml has been updated with:
```yaml
buildCommand: pip install -r requirements.txt
startCommand: python hyperliquid_bot/main.py --strategy stochastic_rsi_link
```

## Deployment Steps

1. **Commit and Push Changes**:
   ```bash
   git add render.yaml
   git commit -m "Fix Render deployment paths and strategy name"
   git push
   ```

2. **Update Render Service**:
   - Go to your Render dashboard
   - Navigate to your `hyperliquid-trading-bot` service
   - Click "Manual Deploy" > "Deploy latest commit"

3. **Monitor Deployment**:
   - Watch the deployment logs
   - The bot should start without file path errors
   - Verify it shows: `Strategy: stochastic_rsi_link`

## Verification Checklist

After deployment, verify:
- [ ] No "file not found" errors
- [ ] Bot starts with correct strategy: `stochastic_rsi_link`
- [ ] Symbol is `LINK`
- [ ] Discord notifications are working
- [ ] No `rsi_pengu` references in logs

## Alternative Solutions

If issues persist, you can also:

1. **Update Start Command in Render Dashboard**:
   - Go to Settings > Start Command
   - Set to: `cd hyperliquid_bot && python main.py --strategy stochastic_rsi_link`

2. **Use Absolute Path**:
   - Set start command to: `python /opt/render/project/src/hyperliquid_bot/main.py --strategy stochastic_rsi_link`

## Important Notes

- The bot code is in the `hyperliquid_bot/` subdirectory
- Strategy name must be `stochastic_rsi_link` (not `rsi_pengu`)
- All environment variables should be set in Render dashboard, not in render.yaml