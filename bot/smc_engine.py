import pandas as pd
import numpy as np
from loguru import logger

class SMCEngine:
    """
    Smart Money Concepts: Order Blocks, Fair Value Gaps, Break of Structure, Change of Character.
    """
    def __init__(self, config):
        self.ob_lookback = config['indicators']['smc']['ob_lookback']
        self.fvg_min_gap = config['indicators']['smc']['fvg_min_gap_pct'] / 100

    def detect_order_blocks(self, df: pd.DataFrame):
        # Simplified: bullish OB = last bearish candle before a break higher
        obs = []
        if len(df) < self.ob_lookback + 2: return obs
        for i in range(self.ob_lookback, len(df)-1):
            # Break of previous high (BOS)
            if df['high'].iloc[i] > df['high'].iloc[i-1]:
                # Find last bearish candle within lookback
                for j in range(i-1, max(i-self.ob_lookback, 0), -1):
                    if df['close'].iloc[j] < df['open'].iloc[j]:
                        ob = {'index': df.index[j], 'top': df['open'].iloc[j], 'bottom': df['low'].iloc[j],
                              'type': 'bullish', 'origin': df.index[j]}
                        obs.append(ob)
                        break
            # Break of previous low (bearish OB)
            if df['low'].iloc[i] < df['low'].iloc[i-1]:
                for j in range(i-1, max(i-self.ob_lookback, 0), -1):
                    if df['close'].iloc[j] > df['open'].iloc[j]:
                        ob = {'index': df.index[j], 'top': df['high'].iloc[j], 'bottom': df['close'].iloc[j],
                              'type': 'bearish', 'origin': df.index[j]}
                        obs.append(ob)
                        break
        return obs

    def detect_fvg(self, df: pd.DataFrame):
        fvgs = []
        for i in range(1, len(df)-1):
            prev_high, prev_low = df['high'].iloc[i-1], df['low'].iloc[i-1]
            next_low, next_high = df['low'].iloc[i+1], df['high'].iloc[i+1]
            gap_up = next_low - prev_high
            gap_down = prev_low - next_high
            if gap_up > 0 and (gap_up / prev_high) > self.fvg_min_gap:
                fvgs.append({'index': df.index[i], 'type': 'bullish', 'top': next_low, 'bottom': prev_high})
            elif gap_down > 0 and (gap_down / prev_high) > self.fvg_min_gap:
                fvgs.append({'index': df.index[i], 'type': 'bearish', 'top': prev_low, 'bottom': next_high})
        return fvgs

    def detect_bos_choch(self, df: pd.DataFrame):
        bos = []
        choch = []
        swing_highs = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
        swing_lows = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
        for idx in df.index[2:-2]:
            if swing_highs.loc[idx]:
                bos.append({'index': idx, 'type': 'BOS_high'})
            if swing_lows.loc[idx]:
                bos.append({'index': idx, 'type': 'BOS_low'})
        # CHOCH: break of last swing low/high
        # Simplified: later
        return bos, choch

    def liquidity_zones(self, df: pd.DataFrame):
        # Equal highs/lows clusters
        highs = df['high'].value_counts()
        lows = df['low'].value_counts()
        lq_high = highs[highs > 2].index.tolist()  # levels touched 3+ times
        lq_low = lows[lows > 2].index.tolist()
        return {'high_liquidity': lq_high, 'low_liquidity': lq_low}
