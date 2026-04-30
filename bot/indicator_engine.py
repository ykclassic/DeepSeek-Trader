import pandas as pd
import pandas_ta_classic as ta
import numpy as np
from loguru import logger
import yaml

class IndicatorEngine:
    def __init__(self, config):
        self.cfg = config['indicators']

    def compute_all(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {}
        ohlc = df[['open', 'high', 'low', 'close']]
        vol = df['volume']

        ind = {}

        # ====================================================
        # Trend & Structure Layer
        # ====================================================
        ind['ema_ribbon'] = {f'ema_{p}': ta.ema(df['close'], length=p) for p in self.cfg['ema_ribbon']}
        ind['sma_50'] = ta.sma(df['close'], length=self.cfg['sma']['fast'])
        ind['sma_200'] = ta.sma(df['close'], length=self.cfg['sma']['slow'])
        ind['supertrend'] = ta.supertrend(
            df['high'], df['low'], df['close'],
            length=self.cfg['supertrend']['atr_period'],
            multiplier=self.cfg['supertrend']['multiplier']
        )

        # Ichimoku – pandas-ta may return a tuple (DataFrame, DataFrame)
        ichi_result = ta.ichimoku(
            df['high'], df['low'], df['close'],
            tenkan=self.cfg['ichimoku']['tenkan'],
            kijun=self.cfg['ichimoku']['kijun'],
            senkou_b=self.cfg['ichimoku']['senkou_b']
        )
        if isinstance(ichi_result, tuple):
            ichi_df = ichi_result[0]        # main DataFrame
        else:
            ichi_df = ichi_result

        wanted_columns = ['ISA_9', 'ISB_26', 'ITS_9', 'IKS_26', 'ICS_26']
        ind['ichimoku'] = {col: ichi_df[col] for col in wanted_columns if col in ichi_df.columns}

        ind['psar'] = ta.psar(
            df['high'], df['low'], df['close'],
            af0=self.cfg['psar']['acceleration'],
            max_af=self.cfg['psar']['maximum']
        )

        # ====================================================
        # Momentum Layer
        # ====================================================
        ind['rsi'] = ta.rsi(df['close'], length=self.cfg['rsi']['period'])
        macd = ta.macd(
            df['close'],
            fast=self.cfg['macd']['fast'],
            slow=self.cfg['macd']['slow'],
            signal=self.cfg['macd']['signal']
        )
        ind['macd'] = macd
        ind['stoch_rsi'] = ta.stochrsi(
            df['close'],
            k=self.cfg['stoch_rsi']['k'],
            d=self.cfg['stoch_rsi']['d'],
            smooth_k=self.cfg['stoch_rsi']['smooth']
        )
        ind['cci'] = ta.cci(df['high'], df['low'], df['close'], length=self.cfg['cci'])
        ind['mfi'] = ta.mfi(df['high'], df['low'], df['close'], vol, length=self.cfg['mfi'])
        ind['williams_r'] = ta.willr(df['high'], df['low'], df['close'], length=self.cfg['williams_r'])
        ind['roc'] = ta.roc(df['close'], length=self.cfg['roc'])

        # ====================================================
        # Volatility Layer
        # ====================================================
        bb = ta.bbands(df['close'], length=self.cfg['bb']['period'], std=self.cfg['bb']['std'])
        ind['bb'] = bb
        ind['kc'] = ta.kc(
            df['high'], df['low'], df['close'],
            length=self.cfg['kc']['period'],
            scalar=self.cfg['kc']['atr_mult']
        )
        ind['atr'] = ta.atr(df['high'], df['low'], df['close'], length=self.cfg['atr'])
        ind['donchian'] = ta.donchian(df['high'], df['low'], length=self.cfg['donchian'])
        log_ret = np.log(df['close'] / df['close'].shift(1))
        rolling_std = log_ret.rolling(window=self.cfg['hv_percentile']['period']).std()
        ind['hv_percentile'] = rolling_std.rank(pct=True)

        # ====================================================
        # Volume & Order Flow
        # ====================================================
        ind['obv'] = ta.obv(df['close'], vol)
        ind['vwap'] = ta.vwap(df['high'], df['low'], df['close'], vol)
        ind['cmf'] = ta.cmf(df['high'], df['low'], df['close'], vol, length=self.cfg['chaikin_mf'])   # Fixed

        # CVD approximation: (close-low)-(high-close) / range * volume
        high_low = df['high'] - df['low']
        high_low[high_low == 0] = np.nan
        buy_pressure = (df['close'] - df['low']) / high_low * vol
        sell_pressure = (df['high'] - df['close']) / high_low * vol
        delta = buy_pressure - sell_pressure
        ind['cvd'] = delta.cumsum().fillna(0)

        return ind
