# 🚀 Render.com Deployment Guide

## Quick Deploy Checklist

### ✅ Repository Ready
- [x] Code pushed to GitHub: https://github.com/ryolangatta/trading-bot-hyperliquid-tama4
- [x] All dependencies in requirements.txt
- [x] render.yaml configuration file included
- [x] .env.template provided for configuration reference

### 🔧 Pre-Deployment Setup

1. **Create Render Account**: https://render.com
2. **Prepare Environment Variables** (copy from your local .env):
   ```
   DRY_RUN=false                     # Set to false for live trading
   TESTNET=false                     # Set to false for mainnet
   HYPERLIQUID_PRIVATE_KEY=0x...     # Your actual private key
   DISCORD_WEBHOOK_URL=https://...   # Your Discord webhook
   ```

### 🎯 Deployment Steps

#### Step 1: Create New Service
1. Login to Render.com
2. Click "New +" → "Background Worker"
3. Connect GitHub → Select "trading-bot-hyperliquid-tama4"
4. **Service Configuration**:
   - **Name**: `hyperliquid-trading-bot`
   - **Environment**: `Python 3`
   - **Region**: `Oregon` (lowest latency)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py --strategy rsi_pengu`
   - **Plan**: `Starter` ($7/month)

#### Step 2: Environment Variables
Add these in Render Dashboard → Environment:

**Trading Settings**:
```
DRY_RUN=false
TESTNET=false
LEVERAGE=10
POSITION_SIZE_PERCENT=1.0
STOP_LOSS_PERCENT=2.5
```

**Strategy Configuration**:
```
STRATEGY_NAME=rsi_pengu
SYMBOL=PENGU
TIMEFRAME=30m
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
```

**API Credentials** (CRITICAL - Keep Secret):
```
HYPERLIQUID_PRIVATE_KEY=your_actual_private_key_here
DISCORD_WEBHOOK_URL=your_actual_webhook_url_here
```

**System Settings**:
```
LOG_LEVEL=INFO
CIRCUIT_BREAKER_ERRORS=5
CIRCUIT_BREAKER_WINDOW_HOURS=1
RETRY_ATTEMPTS=3
RETRY_DELAY=1.0
DISCORD_STATUS_INTERVAL=600
DISCORD_ROI_INTERVAL=3600
```

#### Step 3: Deploy
1. Click "Create Background Worker"
2. Monitor build logs for success
3. Check service logs for "Bot execution started"
4. Verify Discord notification received

### 📊 Post-Deployment Monitoring

#### Immediate Checks (First Hour)
- [ ] Bot startup notification in Discord
- [ ] No error messages in Render logs
- [ ] Market data being fetched successfully
- [ ] RSI calculations working

#### Daily Monitoring
- [ ] Discord status updates every 10 minutes
- [ ] ROI graphs sent hourly
- [ ] No circuit breaker activations
- [ ] Position management working correctly

### 🚨 Emergency Procedures

#### Immediate Stop Trading
1. **Option A**: Set `DRY_RUN=true` in Render environment variables
2. **Option B**: Suspend service in Render dashboard
3. **Option C**: Change Discord webhook to get notifications about manual intervention needed

#### Update Trading Parameters
```bash
# Change position size, stop loss, etc.
# Update environment variables in Render dashboard
# Service will restart automatically
```

### 🔍 Troubleshooting

#### Common Issues
1. **Build Failures**: Check requirements.txt dependencies
2. **API Errors**: Verify private key format and permissions
3. **No Trading**: Confirm DRY_RUN=false and sufficient balance
4. **Discord Silent**: Check webhook URL and channel permissions

#### Log Analysis
```bash
# Key log messages to watch for:
✅ "Bot execution started"
✅ "Hyperliquid client connected"
✅ "All components initialized successfully"
❌ "Circuit breaker active"
❌ "Failed to place order"
❌ "Max retries exceeded"
```

### 💰 Cost Estimation

- **Render Starter Plan**: $7/month
- **Expected Uptime**: 99.9%
- **Resource Usage**: ~100MB RAM, minimal CPU
- **Data Transfer**: ~1GB/month

### 🛡️ Security Reminders

- ✅ Repository is private
- ✅ Private keys only in Render environment variables
- ✅ No secrets committed to code
- ✅ Discord webhook secured
- ✅ Regular monitoring enabled

---

## 🎯 You're Ready to Deploy!

Your Hyperliquid Trading Bot v5.0.0 is production-ready with:
- Professional-grade architecture ✅
- Security-hardened code ✅  
- Comprehensive error handling ✅
- Real-time monitoring ✅
- Automated restart capabilities ✅

**⚠️ Final Warning**: Start with DRY_RUN=true to test, then switch to DRY_RUN=false when confident!