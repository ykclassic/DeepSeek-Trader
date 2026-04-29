import yaml
import time
import schedule
from loguru import logger
from bot.data_fetcher import DataFetcher
from bot.indicator_engine import IndicatorEngine
from bot.strategy_engine import StrategyEngine
from bot.consensus_scorer import ConsensusScorer
from bot.risk_manager import RiskManager
from bot.signal_formatter import create_embed
from bot.discord_notifier import DiscordNotifier
import os
from dotenv import load_dotenv

load_dotenv()

def setup_logging():
    logger.add("logs/signal_bot_{time}.log", rotation="1 day", level="INFO")

def load_config():
    with open("config/settings.yaml") as f:
        return yaml.safe_load(f)

def run_pipeline():
    config = load_config()
    fetcher = DataFetcher(config)
    notifier = DiscordNotifier()
    risk_mgr = RiskManager(config)

    if risk_mgr.check_kill_switch():
        logger.warning("System paused / kill switch active.")
        notifier.log_message("⚠️ Signal generation paused (risk circuit breaker).")
        return

    for symbol in config['app']['symbols']:
        for tf in config['app']['timeframes']:
            df = fetcher.fetch_ohlcv(symbol, tf)
            if df.empty: continue
            indicator_engine = IndicatorEngine(config)
            ind_values = indicator_engine.compute_all(df)
            # onchain data
            onchain_data = {'mvrv_z': 0, 'puell': 0}  # use fetcher in production
            market_data = {'close': df['close'].values, 'onchain': onchain_data,
                           'fear_greed': 50}  # placeholder
            strat = StrategyEngine(config, fetcher)
            raw_signals = strat.evaluate_all(df, symbol, tf)
            for signal in raw_signals:
                # Score
                scorer = ConsensusScorer(config)
                score = scorer.score_signal(signal, ind_values, market_data)
                if score < scorer.min_score:
                    continue
                # Risk check
                if not risk_mgr.can_open_trade(signal):
                    continue
                # Position sizing (simplified)
                entry_avg = (signal['entry_low'] + signal['entry_high']) / 2
                atr = ind_values['atr'].iloc[-1]
                stop_distance = abs(entry_avg - signal['stop'])
                if stop_distance <= 0: continue
                risk_reward = (signal['targets'][0] - entry_avg) / stop_distance if signal['direction'] == 'LONG' else (entry_avg - signal['targets'][0]) / stop_distance
                if risk_reward < config['risk']['min_rr_ratio']:
                    continue
                # Build embed
                embed = create_embed(signal, score, risk_reward, {})
                high_conv = score >= scorer.high_conv
                notifier.send_signal(embed, high_conv)
                logger.success(f"Sent {signal['strategy']} signal {signal['direction']} for {symbol} (score: {score:.1f})")
            # On-chain alerts can be sent separately
            logger.info(f"Finished {symbol} {tf}")

def main():
    setup_logging()
    config = load_config()
    # If running via GitHub Actions or cron, just run once.
    # If long-running VPS, schedule.
    if os.getenv("GITHUB_ACTIONS") == "true":
        run_pipeline()
    else:
        interval = config['app']['run_interval_minutes']
        schedule.every(interval).minutes.do(run_pipeline)
        logger.info(f"Scheduler started, running every {interval} min.")
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()
