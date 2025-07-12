# Hyperliquid Trading Bot v5.2.0

Professional-grade automated trading bot for Hyperliquid DEX with Stochastic RSI strategy.

## 🚀 Features

- **Professional Architecture**: Async Python with modular design
- **Stochastic RSI Strategy**: Long-only momentum trading on LINK with 86.7% win rate
- **Fee Optimization**: Filters unprofitable trades before execution
- **Error Handling**: Circuit breaker with configurable thresholds
- **State Management**: Restart-safe position and ROI persistence
- **Enhanced Discord Integration**: Real-time alerts with ROI visualization
  - Status updates with ROI graphs every 10 minutes
  - Instant trade execution notifications
- **Dual Deployment**: Works on Render and local environments
- **Production Ready**: Comprehensive logging and monitoring

## 📊 Strategy Performance (Stochastic RSI on LINK)

- **Win Rate**: 86.7% (13 wins out of 15 trades)
- **Total Return**: +130.14%
- **Sharpe Ratio**: 1.56 (excellent risk-adjusted returns)
- **Win/Loss Ratio**: 6.50
- **Max Drawdown**: -24.36%
- **Trade Frequency**: Momentum-based (oversold/overbought signals)

## 🛠️ Installation

### Prerequisites

- Python 3.9+
- Hyperliquid account with API access
- Discord webhook for notifications

### Setup

1. **Clone and install**:
   ```bash
   git clone <repository>
   cd hyperliquid_bot
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

3. **Create required directories**:
   ```bash
   mkdir -p logs state
   ```

## ⚙️ Configuration

### Required Settings

```env
# Trading Configuration
DRY_RUN=false                    # Set to true for testing
TESTNET=false                    # Set to true for testnet
HYPERLIQUID_PRIVATE_KEY=your_key # Your Hyperliquid private key
DISCORD_WEBHOOK_URL=your_webhook # Discord webhook URL

# Strategy Parameters
SYMBOL=PENGU
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70

# Risk Management
POSITION_SIZE_PERCENT=1.0        # 1% of capital per trade
STOP_LOSS_PERCENT=2.5           # 2.5% stop loss
LEVERAGE=10                     # 10x isolated leverage
```

### Circuit Breaker Settings

```env
CIRCUIT_BREAKER_ERRORS=5        # Errors before pause
CIRCUIT_BREAKER_WINDOW_HOURS=1  # Time window for counting
```

## 📲 Discord Notifications

The bot provides comprehensive Discord integration with enhanced ROI tracking:

### 🤖 Enhanced Status Updates (Every 10 Minutes)
- **Bot Health Monitoring**: Real-time status, uptime, error tracking
- **Strategy Metrics**: Current Stochastic RSI and RSI values
- **Position & Balance**: Current positions and wallet information
- **ROI Performance**: Total ROI %, Win Rate %, Total Trades
- **Visual ROI Chart**: Interactive performance graph with trade history


### 🔔 Real-Time Trade Alerts
- **Instant Notifications**: Immediate alerts for all trade executions
- **Trade Details**: Symbol, action, price, size, P&L, fees
- **Account Updates**: Real-time wallet balance and available funds
- **Risk Monitoring**: Position status and leverage tracking

### ⚙️ Configuration
```env
# Discord Settings
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_STATUS_INTERVAL=600      # Status updates every 10 minutes
```

## 🚀 Usage

### Local Deployment

```bash
# Dry run mode (recommended for testing)
python main.py --dry-run --log-level DEBUG

# Live trading
python main.py --strategy stochastic_rsi_link

# With custom config
python main.py --config production.env
```

### Render Deployment

1. **Connect your repository** to Render
2. **Create a Background Worker** with:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py --strategy stochastic_rsi_link`
   - **Environment**: Add all variables from `.env`

### Docker Deployment (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py", "--strategy", "stochastic_rsi_link"]
```

## 🎯 Manual Trading

For testing and manual intervention, the bot includes a manual signal system:

### Manual Signal Commands
```bash
# Send manual BUY signal at market price
python manual_signal.py buy 0 "Manual test buy"

# Send manual SELL signal at market price  
python manual_signal.py sell 0 "Manual test sell"

# Check bot status and account balance
python manual_signal.py status
```

### Features
- **Market Order Execution**: Uses IOC limit orders with aggressive pricing for immediate fills
- **Position Management**: Automatically calculates position sizes and validates minimum requirements
- **Risk Validation**: Confirms live trading operations with user prompts
- **State Integration**: Updates bot state and ROI tracking

## 📈 Monitoring & Observability

### Logging

- **Rotating Logs**: 5MB max, 3 backups
- **Secret Masking**: Automatic in logs
- **Structured Format**: Timestamp, level, message

### Circuit Breaker

- **Auto-pause**: After 5 errors in 1 hour
- **Auto-resume**: After 1 hour cooldown
- **Manual Override**: Available via logs

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Test specific components
python -m pytest tests/test_rsi_strategy.py -v
python -m pytest tests/test_fee_calculator.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Integration Tests

```bash
# Full integration tests
python -m pytest tests/test_integration.py -v

# Test with testnet
TESTNET=true python -m pytest tests/test_integration.py
```

## 📁 Project Structure

```
hyperliquid_bot/
├── main.py                 # Entry point
├── config.py               # Configuration management
├── bot_orchestrator.py     # Main execution engine
├── strategies/             # Trading strategies
│   └── stochastic_rsi_link_strategy.py
├── hyperliquid/           # API client wrapper
│   └── hyperliquid_client.py
├── risk/                  # Risk management
│   └── fee_calculator.py
├── state/                 # State persistence
│   └── state_manager.py
├── notifications/         # Discord integration
│   └── discord_notifier.py
├── utils/                 # Utilities
│   ├── logger.py
│   └── error_monitor.py
└── tests/                 # Test suite
```

## 🔒 Security

- **Private Key**: Never logged or transmitted
- **Environment Variables**: Secure configuration
- **Secret Masking**: Automatic in all logs
- **Rate Limiting**: Built-in API protection
- **Input Validation**: All parameters validated

## 🚨 Error Handling

### Circuit Breaker

The bot automatically pauses trading when:
- 5+ errors occur within 1 hour
- Critical system failures detected
- API connectivity issues persist

### Recovery Mechanisms

- **Exponential Backoff**: For transient errors
- **State Recovery**: Positions restored on restart
- **Health Checks**: Continuous API monitoring
- **Discord Alerts**: Immediate error notifications

## 📊 Performance Monitoring

### Key Metrics

- **ROI Tracking**: Cumulative and per-trade
- **Win Rate**: Success percentage
- **Drawdown**: Maximum loss from peak
- **Sharpe Ratio**: Risk-adjusted returns
- **Error Rate**: System reliability

### Dashboard

Discord provides:
- Real-time status updates
- Performance graphs
- Trade execution alerts
- Error notifications

## 🔧 Troubleshooting

### Common Issues

1. **API Connection Errors**:
   ```bash
   # Check network connectivity
   # Verify private key
   # Confirm API permissions
   ```

2. **Configuration Errors**:
   ```bash
   # Validate .env file
   # Check required variables
   # Verify webhook URL
   ```

3. **State Corruption**:
   ```bash
   # Delete state files to reset
   rm state/bot_state.json state/roi_data.json
   ```

### Debug Mode

```bash
python main.py --log-level DEBUG --dry-run
```

## 📝 Changelog

### v5.2.0 (Latest) - Enhanced Discord ROI Integration
- ✅ **Enhanced Status Updates**: Added ROI graphs to 10-minute status updates
- ✅ **Market Order Implementation**: Fixed float_to_wire errors with proper decimal rounding
- ✅ **Manual Signal System**: Added manual BUY/SELL commands with market order execution
- ✅ **Improved Documentation**: Updated CLAUDE.md and README with detailed specifications
- ✅ **Production Ready**: Comprehensive error handling and circuit breaker integration

### v5.1.0 - Stochastic RSI Strategy
- ✅ **Strategy Migration**: Migrated from RSI to Stochastic RSI on LINK
- ✅ **Performance Optimization**: 86.7% win rate with 1.56 Sharpe ratio
- ✅ **Risk Management**: Enhanced position sizing and stop loss implementation

### v5.0.0 - Production Foundation
- ✅ **Professional Architecture**: Async Python with modular design
- ✅ **Official SDK Integration**: Hyperliquid Python SDK implementation
- ✅ **Production Features**: Error monitoring, health checks, state management
- ✅ **Discord Integration**: Real-time notifications and basic ROI tracking

## 📄 License

This project is for educational and research purposes. Use at your own risk.

## ⚠️ Disclaimer

- **High Risk**: Crypto trading involves substantial risk
- **No Guarantees**: Past performance doesn't predict future results
- **Testing Required**: Always test thoroughly before live trading
- **Risk Management**: Never risk more than you can afford to lose

## 🤝 Support

For issues and questions:
1. Check the logs for error details
2. Review configuration settings
3. Test in dry-run mode first
4. Monitor Discord alerts

---

**Version**: 5.0.0  
**Last Updated**: 2025-07-07  
**Specification**: See CLAUDE.md for detailed requirements