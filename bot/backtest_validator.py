import pandas as pd
from bot.data_fetcher import DataFetcher
from bot.indicator_engine import IndicatorEngine
from bot.strategy_engine import StrategyEngine
from bot.consensus_scorer import ConsensusScorer
from bot.risk_manager import RiskManager
import yaml
from loguru import logger

def run_backtest():
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)
    fetcher = DataFetcher(config)
    df = fetcher.fetch_ohlcv("BTC/USDT", "1h", 500)
    strat = StrategyEngine(config, fetcher)
    signals = strat.evaluate_all(df, "BTC/USDT", "1h")
    logger.info(f"Backtest signals generated: {len(signals)}")
    # Simple walk-forward: log signals with exit conditions
    # Full backtest would simulate trades
    for sig in signals:
        logger.info(f"Signal: {sig['strategy']} {sig['direction']} @ {sig['entry_low']:.2f}")
if __name__ == "__main__":
    run_backtest()
