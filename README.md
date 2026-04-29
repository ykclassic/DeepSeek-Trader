# Unified Crypto Signal Engine

Production-grade multi-strategy signal bot covering:
- Indicator Suite (Trend, Momentum, Volatility, Volume, SMC, On-Chain)
- 8 Strategy Engines
- Confluence Scoring (0–10)
- Risk Management (ATR stops, RRR filter, drawdown circuit breaker)
- Discord Delivery via Webhook

## Setup
1. Clone repo: `git clone ...`
2. Copy `config/.env.example` to `.env` and fill API keys.
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python -m bot.main`

## Deployment
- Option 1: GitHub Actions (free, every 4H + market hours)
- Option 2: Oracle Free Tier VPS (24/7)
- Docker: `docker-compose up -d`
