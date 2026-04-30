 import pandas as pd
import numpy as np
from loguru import logger
from bot.indicator_engine import IndicatorEngine
from bot.smc_engine import SMCEngine
from bot.onchain_engine import OnchainEngine
from bot.data_fetcher import DataFetcher
import yaml

class StrategyEngine:
    def __init__(self, config, fetcher: DataFetcher):
        self.cfg = config
        self.fetcher = fetcher
        self.ind_engine = IndicatorEngine(config)
        self.smc = SMCEngine(config)
        self.onchain_engine = OnchainEngine(fetcher)

    def evaluate_all(self, df: pd.DataFrame, symbol: str, timeframe: str,
                     onchain_data: dict, derivatives: dict,
                     liquidation_levels: list = None) -> list:
        if df.empty:
            return []
        ind = self.ind_engine.compute_all(df)
        smc_data = {
            'obs': self.smc.detect_order_blocks(df),
            'fvgs': self.smc.detect_fvg(df),
            'bos': self.smc.detect_bos(df, *self.smc.find_swing_points(df)),
            'choch': self.smc.detect_choch(df, *self.smc.find_swing_points(df)),
            'liquidity_zones': self.smc.liquidity_zones(df)
        }

        signals = []
        signals.append(self._trend_rider(df, ind, onchain_data))
        signals.append(self._breakout_squeeze(df, ind))
        signals.append(self._mean_reversion(df, ind, derivatives))
        signals.append(self._smc_signal(df, ind, smc_data))
        signals.append(self._vwap_reversion(df, ind))
        signals.append(self._funding_fade(derivatives, df['close'].iloc[-1]))
        signals.append(self._liquidation_sweep(df, liquidation_levels))
        signals.append(self._onchain_alpha(onchain_data, derivatives, df['close'].iloc[-1]))

        valid = [s for s in signals if s is not None]
        for s in valid:
            s['symbol'] = symbol
            s['timeframe'] = timeframe
        return valid

    def _trend_rider(self, df, ind, onchain):
        close = df['close'].iloc[-1]
        ema200 = ind['ema_ribbon']['ema_200'].iloc[-1]
        ema50 = ind['ema_ribbon']['ema_50'].iloc[-1]
        rsi = ind['rsi'].iloc[-1]
        macd_hist = ind['macd']['MACDh_12_26_9'].iloc[-1]
        if close > ema200 and ema50 > ema200 and macd_hist > 0 and 50 <= rsi <= 70:
            pullback_ema = ind['ema_ribbon'].get('ema_21', pd.Series()).iloc[-1]
            entry = pullback_ema if pullback_ema and close > pullback_ema else close
            stop = ind['supertrend']['SUPERT_10_3.0'].iloc[-1]
            targets = [close + atr for atr in [ind['atr'].iloc[-1]*1.5, ind['atr'].iloc[-1]*3.0]]
            return {'strategy': 'Trend Rider', 'direction': 'LONG',
                    'entry_low': min(entry, entry*0.999), 'entry_high': entry*1.001,
                    'stop': stop, 'targets': targets, 'confidence': 7.0}
        return None

    def _breakout_squeeze(self, df, ind):
        bb = ind['bb']
        kc = ind['kc']
        close = df['close'].iloc[-1]
        squeeze = (bb['BBL_20_2.0'] > kc['KCLe_20_1.5']) & (bb['BBU_20_2.0'] < kc['KCUe_20_1.5'])
        if len(squeeze) >= self.cfg['strategies']['breakout']['squeeze_bars']:
            recent = squeeze.iloc[-self.cfg['strategies']['breakout']['squeeze_bars']:]
            if all(recent):
                vol_sma = df['volume'].rolling(20).mean()
                if df['volume'].iloc[-1] > self.cfg['strategies']['breakout']['volume_spike_mult'] * vol_sma.iloc[-1]:
                    atr = ind['atr'].iloc[-1]
                    return {'strategy': 'Breakout Squeeze', 'direction': 'LONG',
                            'entry_low': close, 'entry_high': close*1.005,
                            'stop': close - 2*atr, 'targets': [close+atr, close+2*atr],
                            'confidence': 7.5}
        return None

    def _mean_reversion(self, df, ind, derivatives):
        rsi = ind['rsi'].iloc[-1]
        cci = ind['cci'].iloc[-1]
        close = df['close'].iloc[-1]
        funding = derivatives.get('funding_rate', 0)
        if rsi < 30 and cci < -100 and funding < 0.001:
            atr = ind['atr'].iloc[-1]
            target = ind['vwap'].iloc[-1] if 'vwap' in ind else ind['bb']['BBM_20_2.0'].iloc[-1]
            return {'strategy': 'Mean Reversion', 'direction': 'LONG',
                    'entry_low': close, 'entry_high': close,
                    'stop': close - 2*atr, 'targets': [target], 'confidence': 5.5}
        if rsi > 70 and cci > 100 and funding > 0.001:
            return {'strategy': 'Mean Reversion', 'direction': 'SHORT',
                    'entry_low': close, 'entry_high': close,
                    'stop': close + 2*atr, 'targets': [ind['vwap'].iloc[-1]], 'confidence': 5.5}
        return None

    def _smc_signal(self, df, ind, smc_data):
        if not smc_data['obs'] or not smc_data['fvgs']:
            return None
        for ob in smc_data['obs'][-3:]:
            for fvg in smc_data['fvgs'][-5:]:
                if ob['type'] == 'bullish' and fvg['type'] == 'bullish':
                    if ob['top'] >= fvg['top'] and ob['bottom'] <= fvg['bottom']:
                        entry_high = fvg['top']
                        entry_low = fvg['bottom']
                        stop = ob['bottom']
                        risk = entry_high - stop
                        return {'strategy': 'SMC', 'direction': 'LONG',
                                'entry_low': entry_low, 'entry_high': entry_high,
                                'stop': stop,
                                'targets': [entry_high + risk, entry_high + 2*risk],
                                'confidence': 9.0}
        return None

    def _vwap_reversion(self, df, ind):
        if 'vwap' not in ind:
            return None
        vwap_series = ind['vwap']
        close = df['close']
        rolling_std = (close - vwap_series).rolling(20).std()
        deviation = (close - vwap_series) / rolling_std
        last_dev = deviation.iloc[-1]
        if last_dev > self.cfg['strategies']['vwap_reversion']['sd_threshold']:
            atr = ind['atr'].iloc[-1]
            return {'strategy': 'VWAP Reversion', 'direction': 'SHORT',
                    'entry_low': close.iloc[-1], 'entry_high': close.iloc[-1],
                    'stop': close.iloc[-1] + 2*atr, 'targets': [vwap_series.iloc[-1]],
                    'confidence': 6.0}
        if last_dev < -self.cfg['strategies']['vwap_reversion']['sd_threshold']:
            atr = ind['atr'].iloc[-1]
            return {'strategy': 'VWAP Reversion', 'direction': 'LONG',
                    'entry_low': close.iloc[-1], 'entry_high': close.iloc[-1],
                    'stop': close.iloc[-1] - 2*atr, 'targets': [vwap_series.iloc[-1]],
                    'confidence': 6.0}
        return None

    def _funding_fade(self, derivatives, price):
        fund = derivatives.get('funding_rate', 0)
        ls = derivatives.get('long_short_ratio', 1)
        if fund > self.cfg['strategies']['funding_fade']['funding_limit'] and \
           ls > self.cfg['strategies']['funding_fade']['ls_ratio_limit']:
            return {'strategy': 'Funding Fade', 'direction': 'SHORT',
                    'entry_low': price, 'entry_high': price,
                    'stop': price*1.02, 'targets': [price*0.98, price*0.96],
                    'confidence': 6.5}
        return None

    def _liquidation_sweep(self, df, liquidation_levels):
        if not liquidation_levels:
            return None
        levels = [(liq['price'], liq['size']) for liq in liquidation_levels if 'price' in liq and 'size' in liq]
        if not levels:
            return None
        levels.sort(key=lambda x: x[1], reverse=True)
        target_price = levels[0][0]
        recent_candles = df.iloc[-5:]
        swept = any(candle['low'] <= target_price <= candle['high'] for _, candle in recent_candles.iterrows())
        if swept:
            last_candle = df.iloc[-1]
            if last_candle['close'] > last_candle['open'] and last_candle['low'] <= target_price:
                return {'strategy': 'Liquidation Sweep', 'direction': 'LONG',
                        'entry_low': last_candle['close'], 'entry_high': last_candle['close'],
                        'stop': target_price - recent_candles['low'].min() * 0.005,
                        'targets': [last_candle['close']*1.02, last_candle['close']*1.04],
                        'confidence': 8.0}
        return None

    def _onchain_alpha(self, onchain, derivatives, price):
        mvrv = onchain.get('mvrv_z', 0)
        puell = onchain.get('puell', 0)
        netflow = onchain.get('netflow', 0)
        ssr = onchain.get('ssr', 0)
        if mvrv < self.cfg['strategies']['onchain_bias']['mvrv_buy'] and \
           puell < self.cfg['strategies']['onchain_bias']['puell_buy'] and \
           netflow < 0:
            return {'strategy': 'On-Chain Alpha', 'direction': 'LONG',
                    'entry_low': price, 'entry_high': price,
                    'stop': price*0.9, 'targets': [price*1.3],
                    'confidence': 7.5}
        if mvrv > self.cfg['strategies']['onchain_bias']['mvrv_sell'] and \
           puell > self.cfg['strategies']['onchain_bias']['puell_sell'] and \
           netflow > 0:
            return {'strategy': 'On-Chain Alpha', 'direction': 'SHORT',
                    'entry_low': price, 'entry_high': price,
                    'stop': price*1.1, 'targets': [price*0.7],
                    'confidence': 7.5}
        return None
