import pandas as pd
import numpy as np
from loguru import logger

class SMCEngine:
    def __init__(self, config):
        self.ob_lookback = config['indicators']['smc']['ob_lookback']
        self.fvg_min_gap = config['indicators']['smc']['fvg_min_gap_pct'] / 100

    def find_swing_points(self, df: pd.DataFrame, window=3):
        """
        Return swing highs/lows index lists.
        """
        high_cond = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1)) & \
                    (df['high'] > df['high'].rolling(window).max().shift(1))
        low_cond = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1)) & \
                   (df['low'] < df['low'].rolling(window).min().shift(1))
        swing_highs = df.index[high_cond].tolist()
        swing_lows = df.index[low_cond].tolist()
        return swing_highs, swing_lows

    def detect_bos(self, df, swing_highs, swing_lows):
        """
        Break of Structure: price exceeds previous swing high/low.
        """
        bos = []
        last_high = None
        last_low = None
        for i in range(1, len(df)):
            idx = df.index[i]
            # bullish BOS
            if last_high and df['close'].iloc[i] > last_high:
                bos.append({'index': idx, 'type': 'BOS_bull', 'level': last_high})
                last_high = df['high'].iloc[i]
            # bearish BOS
            if last_low and df['close'].iloc[i] < last_low:
                bos.append({'index': idx, 'type': 'BOS_bear', 'level': last_low})
                last_low = df['low'].iloc[i]
            # update swing levels
            if idx in swing_highs:
                last_high = df.loc[idx, 'high']
            if idx in swing_lows:
                last_low = df.loc[idx, 'low']
        return bos

    def detect_choch(self, df, swing_highs, swing_lows):
        """
        Change of Character: break of a minor swing structure.
        """
        choch = []
        # Check for bearish CHOCH (break of higher low)
        for i in range(2, len(swing_lows)):
            recent_low = swing_lows[i-1]
            if df.loc[recent_low, 'low'] > df.loc[swing_lows[i-2], 'low']:  # higher low
                # see if later price breaks below that higher low
                mask = df.index > recent_low
                break_idx = df.index[mask & (df['low'] < df.loc[recent_low, 'low'])]
                if not break_idx.empty:
                    choch.append({'index': break_idx[0],
                                  'type': 'CHOCH_bear'})
                    break
        # Check for bullish CHOCH (break of lower high)
        for i in range(2, len(swing_highs)):
            recent_high = swing_highs[i-1]
            if df.loc[recent_high, 'high'] < df.loc[swing_highs[i-2], 'high']:
                mask = df.index > recent_high
                break_idx = df.index[mask & (df['high'] > df.loc[recent_high, 'high'])]
                if not break_idx.empty:
                    choch.append({'index': break_idx[0],
                                  'type': 'CHOCH_bull'})
                    break
        return choch

    def detect_order_blocks(self, df):
        obs = []
        for i in range(self.ob_lookback+1, len(df)):
            # bullish OB: bearish candle followed by price rise breaking its high
            if df['close'].iloc[i] > df['open'].iloc[i]:
                if df['close'].iloc[i-1] < df['open'].iloc[i-1]:
                    ob_high = df['open'].iloc[i-1]
                    ob_low = df['low'].iloc[i-1]
                    obs.append({'index': df.index[i-1], 'top': ob_high, 'bottom': ob_low,
                                'type': 'bullish', 'origin': df.index[i-1]})
        return obs

    def detect_fvg(self, df):
        fvgs = []
        for i in range(1, len(df)-1):
            prev_high = df['high'].iloc[i-1]
            prev_low = df['low'].iloc[i-1]
            next_low = df['low'].iloc[i+1]
            next_high = df['high'].iloc[i+1]
            gap_up = next_low - prev_high
            gap_down = prev_low - next_high
            if gap_up > 0 and (gap_up / prev_high) > self.fvg_min_gap:
                fvgs.append({'index': df.index[i], 'type': 'bullish', 'top': next_low, 'bottom': prev_high})
            if gap_down > 0 and (gap_down / prev_high) > self.fvg_min_gap:
                fvgs.append({'index': df.index[i], 'type': 'bearish', 'top': prev_low, 'bottom': next_high})
        return fvgs

    def liquidity_zones(self, df):
        # round to 2 decimals
        high_counts = df['high'].round(2).value_counts()
        low_counts = df['low'].round(2).value_counts()
        lq_high = high_counts[high_counts > 2].index.tolist()
        lq_low = low_counts[low_counts > 2].index.tolist()
        return {'high_liquidity': lq_high, 'low_liquidity': lq_low}
