# CLAUDE.MD – Hyperliquid Trading Bot Specification

**Version:** 5.2.0  
**Last Updated:** 2025-07-08

---

## 🔗 External References (REQUIRED)

Claude AI must always refer to the following official documentation sources when implementing or modifying any logic related to:

- **Hyperliquid API, strategy integration, wallet auth**:
  - https://hyperliquid.gitbook.io/hyperliquid-docs

- **Render deployment, secrets configuration, build/runtime requirements**:
  - https://render.com/docs

---

## 🌟 Objective

Build a secure, professional-grade execution-only crypto trading bot for Hyperliquid using a single strategy per bot instance.

---

## ✅ Bot Overview

- Live on Hyperliquid Mainnet or Testnet 24/7
- Modular strategy system, but only **one strategy per bot instance**
- Async Python 3 bot with no Redis or database dependency
- Leverage: **10x isolated** (default)
- DRY_RUN + LIVE mode toggle via `.env`
- Real orders via `hyperliquid-python-sdk` using API wallet
- Deployable to Render (background worker) or local PC
- Real-time Discord alerts + ROI tracking
- Sends **bot status updates to Discord every 10 minutes**
- Sends **accumulated ROI graph to Discord every hour**

---

## 📊 Active Strategy: MACD Strategy

**Token:** ARB  
**Timeframe:** 1 hour  
**Position Type:** Long/Short  
**Indicators:** MACD (12, 26, 9)

### Entry Rules
- **Long Entry:** MACD line crosses above signal line AND MACD histogram turns positive
- **Short Entry:** MACD line crosses below signal line AND MACD histogram turns negative
- Additional confirmation: MACD line must be moving away from zero line

### Exit Rules
- **Take Profit:** 2% gain from entry price
- **Stop Loss:** 1% loss from entry price
- **Signal Exit:** MACD line crosses back towards signal line (opposite direction)

### Parameters
- **MACD Fast Period:** 12
- **MACD Slow Period:** 26  
- **MACD Signal Period:** 9
- **Take Profit:** 2.0%
- **Stop Loss:** 1.0%
- **Position Hold Time:** Max 24 hours

### Strategy Mechanics
- Calculate MACD line: EMA(12) - EMA(26)
- Calculate Signal line: EMA(9) of MACD line
- Calculate Histogram: MACD line - Signal line
- Entry on crossover with histogram confirmation
- Exit on TP/SL or reverse signal

### Risk Management
- Stop Loss: 1% below entry (optimized from backtesting)
- Take Profit: 2% above entry (optimized from backtesting)
- Position Sizing: Fixed dollar amounts OR percentage-based (configurable)
  - **POSITION_SIZE_USD**: Fixed dollar amount per trade (e.g., $15.00)
  - **POSITION_SIZE_PERCENT**: 1–2% capital risked per trade (fallback)
  - Dollar amounts take priority over percentage when both are set
- Max Drawdown: 50% (accepted)
- **Portfolio Heat / Correlation Checks: NOT USED**

### Performance Metrics
- **ROI:** 1.25% over 18 days
- **Sharpe Ratio:** 10.25 (excellent risk-adjusted returns)
- **Win Rate:** 59.5%
- **Max Drawdown:** 0.14%
- **Total Trades:** 79 (backtested)
- **Optimal SL/TP:** 1% stop loss, 2% take profit

---

## 🛠️ Error Handling (REQUIRED)

- All trading errors must be caught and logged with timestamp
- Retry logic with exponential backoff for transient errors
- **Circuit breaker:** auto-pauses trading after 5+ errors in 1 hour
- Discord DM alert on fatal crash or trigger
- Bot must attempt self-restart after critical failure (Render-specific)

---

## 💸 Fee Optimization (REQUIRED)

- Include `fee_calculator.py` to filter trades where expected return < fees
- Assume Hyperliquid maker/taker rates from SDK or live API
- No trade should execute if net expected gain is negative

---

## ❌ Data Storage

- Historical data persistence or backtesting **NOT required**
- No Redis / no database
- ROI and trade logs stored to disk only

---

## 🚀 Production Features (IMPLEMENTED)

### ✅ Core Production Components
- `error_monitor.py`: Thread-safe error tracking with circuit breaker
- `health_checker.py`: Comprehensive system/API/trading health monitoring  
- `production_hardening.py`: Security validation and deployment hardening
- `fee_calculator.py`: High-precision decimal arithmetic for fees
- `plot_roi.py`: Real-time ROI chart generation for Discord

### ✅ Security & Stability
- **Atomic file operations** with fcntl locking to prevent data corruption
- **Memory leak prevention** with proper thread cleanup and resource management
- **HTTP connection pooling** for efficient API communication
- **Discord rate limiting** (30 req/min) with exponential backoff
- **Input validation** and division by zero protection throughout

### ✅ Mathematical Accuracy
- **Stochastic RSI calculation** using proper Wilder's smoothing method for RSI with Stochastic overlay (industry standard)
- **High-precision fee calculations** using Decimal arithmetic
- **Flexible position sizing** with dollar amounts and percentage-based options
- **Robust validation** with comprehensive input checks and safety limits

### ✅ Monitoring & Observability
- **Real-time health checks**: CPU, memory, disk, API connectivity
- **Circuit breaker**: Auto-pause after 5+ errors in 1 hour
- **Production hardening**: Resource limits, signal handling, security validation
- **Emergency stop mechanism** for critical situations

---

## 📁 File Structure

```
hyperliquid_bot/
├── main.py                          # Entry point with self-restart logic
├── config.py                        # Configuration management
├── bot_orchestrator.py             # Main bot coordination
├── strategies/
│   └── [strategy_file_to_be_created]  # New strategy implementation
├── hyperliquid_wrapper/
│   └── hyperliquid_client.py       # API client with connection pooling
├── risk/
│   └── fee_calculator.py           # High-precision fee calculations
├── data/                           # Market data utilities
├── state/
│   └── state_manager.py           # Atomic state persistence with locking
├── notifications/
│   └── discord_notifier.py        # Rate-limited Discord integration
├── utils/
│   ├── error_monitor.py           # Thread-safe error tracking
│   ├── health_checker.py          # Production health monitoring
│   ├── production_hardening.py   # Security & deployment hardening
│   ├── plot_roi.py               # ROI chart generation
│   └── logger.py                 # Logging configuration
├── tests/                         # Unit and integration tests
└── .env.template                  # Environment configuration template
```

---

## 🧪 Testing Requirements

- Unit tests for:
  - Entry/Exit logic
  - Fee filtering logic
- Integration tests for:
  - Hyperliquid API (auth, order, cancel)
  - Discord alerts

---

## ✅ Go Live Checklist

### 🔧 Core Requirements
- [x] `.env` set with all live secrets and toggles
- [x] Deployed as Render background worker (Python 3)
- [x] ROI and position resume correctly on restart
- [x] Strategy and fee logic tested in dry run + live
- [x] Circuit breaker + Discord crash alerts enabled
- [x] Logs rotate and redact sensitive info

### 🚀 Production Readiness (v5.2.0)
- [x] **Mathematical accuracy**: Stochastic RSI using Wilder's smoothing method
- [x] **Data integrity**: Atomic file operations with fcntl locking
- [x] **Memory management**: Thread cleanup and resource leak prevention
- [x] **API reliability**: Connection pooling and rate limiting
- [x] **Error handling**: Comprehensive validation and circuit breaker
- [x] **Security hardening**: Input validation and environment checks
- [x] **Health monitoring**: Real-time system/API/trading health checks
- [x] **High precision**: Decimal arithmetic for all financial calculations
- [x] **Flexible position sizing**: Dollar amounts and percentage-based options
- [x] **Production deployment**: Emergency stop and graceful shutdown

---

## 🧠 Claude AI Guidelines

**MANDATORY READING PROTOCOL:**
- **ALWAYS read CLAUDE.md FIRST** before generating any code or making strategy decisions
- **NEVER assume anything** - always read existing code files to understand current implementation
- **READ ALL RELEVANT CODE** before making changes or suggestions
- Reference this specification throughout the entire development process

**DEVELOPMENT RULES:**
- Never hardcode sensitive values
- Validate all config at startup
- Use official docs:
  - https://hyperliquid.gitbook.io/hyperliquid-docs
  - https://render.com/docs