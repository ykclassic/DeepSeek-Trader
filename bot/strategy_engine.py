import pandas as pd
import numpy as np
from loguru import logger
from bot.indicator_engine import IndicatorEngine
from bot.smc_engine import SMCEngine
from bot.onchain_engine import OnchainEngine
import yaml

class StrategyEngine:
    def __init__(self, config, data_fetcher):
        self.cfg = config
        self.indicator = IndicatorEngine(config)
        self.smc = SMCEngine(config)
        self.onchain = OnchainEngine(data_fetcher, config)

    def evaluate_all(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """
        Returns a list of signal dicts (one per strategy) or empty.
        Each signal has: strategy_name, direction, entry_low, entry_high, stop, targets, confidence (preliminary).
        """
        if df.empty: return []
        ind = self.indicator.compute_all(df)
        onchain_data = self.onchain.get_onchain_signals()
        signals = []

        # Strategy A: Trend Rider
        sig_a = self._trend_rider(df, ind, onchain_data)
        if sig_a: signals.append(sig_a)

        # Strategy B: Breakout
        sig_b = self._breakout_squeeze(df, ind)
        if sig_b: signals.append(sig_b)

        # Strategy C: Mean Reversion
        sig_c = self._mean_reversion(df, ind, onchain_data)
        if sig_c: signals.append(sig_c)

        # Strategy D: SMC
        smc_obs = self.smc.detect_order_blocks(df)
        fvgs = self.smc.detect_fvg(df)
        bos, choch = self.smc.detect_bos_choch(df)
        sig_d = self._smc_engine(df, smc_obs, fvgs, bos, choch)
        if sig_d: signals.append(sig_d)

        # Strategy E: VWAP Reversion
        sig_e = self._vwap_reversion(df, ind)
        if sig_e: signals.append(sig_e)

        # Strategy F: Funding Rate / OI
        sig_f = self._funding_fade(onchain_data)
        if sig_f: signals.append(sig_f)

        # Strategy G: Liquidation Sweep (simplified)
        sig_g = self._liquidation_sweep(df)   # placeholder
        # Strategy H: On-Chain Bias
        sig_h = self._onchain_alpha(onchain_data)
        if sig_h: signals.append(sig_h)

        # Enrich with symbol and timeframe
        for s in signals:
            s['symbol'] = symbol
            s['timeframe'] = timeframe
        return signals

    def _trend_rider(self, df, ind, onchain):
        close = df['close'].iloc[-1]
        ema200 = ind['ema_ribbon']['ema_200'].iloc[-1]
        ema50 = ind['ema_ribbon']['ema_50'].iloc[-1]
        rsi = ind['rsi'].iloc[-1]
        macd_hist = ind['macd']['MACDh_12_26_9'].iloc[-1]
        if close > ema200 and ema50 > ema200 and macd_hist > 0 and 50 <= rsi <= 70:
            pullback = df['low'].min() if 'ema_21' in ind['ema_ribbon'] else close * 0.99
            return {
                'strategy': 'Trend Rider',
                'direction': 'LONG',
                'entry_low': pullback,
                'entry_high': close,
                'stop': ind['supertrend']['SUPERT_10_3.0'].iloc[-1],
                'targets': [close * 1.02, close * 1.04],
                'confidence': 6.5
            }
        return None

    def _breakout_squeeze(self, df, ind):
        bb = ind['bb']
        kc = ind['kc']
        close = df['close'].iloc[-1]
        squeeze = (bb['BBL_20_2.0'] > kc['KCLe_20_1.5']) & (bb['BBU_20_2.0'] < kc['KCUe_20_1.5'])
        if squeeze.iloc[-1] == False and squeeze.iloc[-2] == True:  # breakout
            volume = df['volume'].iloc[-1]
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            if volume > 1.5 * avg_vol:
                return {
                    'strategy': 'Breakout Squeeze',
                    'direction': 'LONG',
                    'entry_low': close,
                    'entry_high': close * 1.005,
                    'stop': close - 2 * ind['atr'].iloc[-1],
                    'targets': [close + ind['atr'].iloc[-1], close + 2*ind['atr'].iloc[-1]],
                    'confidence': 7.0
                }
        return None

    def _mean_reversion(self, df, ind, onchain):
        rsi = ind['rsi'].iloc[-1]
        cci = ind['cci'].iloc[-1]
        close = df['close'].iloc[-1]
        if rsi < 30 and cci < -100:
            if onchain.get('funding_rate', 0) < 0.001:  # not extreme
                return {
                    'strategy': 'Mean Reversion',
                    'direction': 'LONG',
                    'entry_low': close,
                    'entry_high': close,
                    'stop': df['low'].min() - ind['atr'].iloc[-1],
                    'targets': [ind['vwap'].iloc[-1], ind['bb']['BBM_20_2.0'].iloc[-1]],
                    'confidence': 5.5
                }
        return None

    def _smc_engine(self, df, obs, fvgs, bos, choch):
        if not obs or not fvgs: return None
        # Find FVG inside OB zone (simplified)
        for ob in obs:
            for fvg in fvgs:
                if ob['type'] == 'bullish' and fvg['type'] == 'bullish':
                    if ob['top'] >= fvg['top'] and ob['bottom'] <= fvg['bottom']:
                        return {
                            'strategy': 'SMC',
                            'direction': 'LONG',
                            'entry_low': fvg['bottom']*0.999,
                            'entry_high': fvg['top'],
                            'stop': ob['bottom'],
                            'targets': [ob['top'] + (ob['top']-ob['bottom']), ob['top'] + 2*(ob['top']-ob['bottom'])],
                            'confidence': 9.0
                        }
        return None

    def _vwap_reversion(self, df, ind):
        # Placeholder: deviation from VWAP
        return None

    def _funding_fade(self, onchain):
        funding = onchain.get('funding_rate', 0)
        ls_ratio = onchain.get('long_short_ratio', 1)
        if funding > 0.001 and ls_ratio > 3:
            return {
                'strategy': 'Funding Fade',
                'direction': 'SHORT',
                'entry_low': 0, 'entry_high': 0,  # will be set from price later
                'confidence': 6.0
            }
        return None

    def _liquidation_sweep(self, df):
        return None  # require exchange heatmap, placeholder

    def _onchain_alpha(self, onchain):
        mvrv = onchain.get('mvrv_z', 0)
        puell = onchain.get('puell', 0)
        netflow = onchain.get('netflow', 0)
        if mvrv < 0 and puell < 0.5 and netflow < 0:
            return {'strategy': 'On-Chain Alpha', 'direction': 'LONG', 'confidence': 7.5}
        return None
