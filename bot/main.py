import yaml
import os
import time
import schedule
from loguru import logger
from dotenv import load_dotenv
from bot.data_fetcher import DataFetcher
from bot.indicator_engine import IndicatorEngine
from bot.strategy_engine import StrategyEngine
from bot.onchain_engine import OnchainEngine
from bot.consensus_scorer import ConsensusScorer
from bot.risk_manager import RiskManager
from bot.signal_formatter import create_embed
from bot.discord_notifier import DiscordNotifier

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
        logger.warning("System paused (kill switch active).")
        notifier.log_message("⚠️ Engine paused due to risk circuit breaker.")
        return

    onchain_engine = OnchainEngine(fetcher)
    onchain_data = onchain_engine.get_full_onchain('BTC')          # global on‑chain for BTC
    derivatives = onchain_engine.get_derivatives('BTC')
    liquidation_levels = onchain_engine.get_liquidation_levels('BTC')

    # Multi‑timeframe signal collection
    tf_signals = {}
    for symbol in config['app']['symbols']:
        tf_signals[symbol] = {}
        for tf in config['app']['timeframes']:
            df = fetcher.fetch_ohlcv(symbol, tf)
            if df.empty:
                continue
            strat = StrategyEngine(config, fetcher)
            # Pass all live data to the strategy engine
            signals = strat.evaluate_all(df, symbol, tf,
                                         onchain_data, derivatives,
                                         liquidation_levels)
            tf_signals[symbol][tf] = signals

    # Score, filter and dispatch signals
    for symbol, tf_dict in tf_signals.items():
        for tf, signals in tf_dict.items():
            for sig in signals:
                # Determine if opposite TF signals same direction (multi‑TF alignment)
                other_tf = [t for t in config['app']['timeframes'] if t != tf]
                aligned = any(
                    any(s['direction'] == sig['direction'] for s in tf_dict.get(ot, []))
                    for ot in other_tf
                )
                df = fetcher.fetch_ohlcv(symbol, tf)
                if df.empty:
                    continue
                ind_engine = IndicatorEngine(config)
                ind_values = ind_engine.compute_all(df)
                scorer = ConsensusScorer(config)
                market_data = {'close': df['close'].values}
                score = scorer.score_signal(sig, ind_values, market_data,
                                            onchain_data, derivatives, aligned)
                if score < scorer.min_score:
                    continue
                if not risk_mgr.can_open_trade(sig):
                    continue
                # Risk / reward calculation
                entry_avg = (sig['entry_low'] + sig['entry_high']) / 2
                atr = ind_values['atr'].iloc[-1]
                stop_dist = abs(entry_avg - sig['stop'])
                if stop_dist <= 0:
                    continue
                if sig['direction'] == 'LONG':
                    rr = (sig['targets'][0] - entry_avg) / stop_dist
                else:
                    rr = (entry_avg - sig['targets'][0]) / stop_dist
                if rr < config['risk']['min_rr_ratio']:
                    continue
                embed = create_embed(sig, score, rr, {})
                high_conv = score >= scorer.high_conv
                notifier.send_signal(embed, high_conv)
                logger.success(f"Sent {sig['strategy']} {sig['direction']} {symbol} {tf} "
                               f"(score {score:.1f}, RR {rr:.2f})")

    notifier.log_message("✅ Signal run completed.")

def main():
    setup_logging()
    config = load_config()
    if os.getenv("GITHUB_ACTIONS") == "true":
        run_pipeline()
    else:
        interval = config['app']['run_interval_minutes']
        schedule.every(interval).minutes.do(run_pipeline)
        logger.info(f"Scheduler started every {interval} minutes.")
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()
