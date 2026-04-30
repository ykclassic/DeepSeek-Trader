import numpy as np
import pandas as pd
from loguru import logger
from bot.sentiment_fetcher import SentimentFetcher

class ConsensusScorer:
    def __init__(self, config):
        self.weights = config['consensus_scoring']['weights']
        self.min_score = config['consensus_scoring']['minimum_fire_score']
        self.high_conv = config['consensus_scoring']['high_conviction_threshold']
        self.sentiment = SentimentFetcher()

    def score_signal(self, signal: dict,
                     ind_values: dict,
                     market_data: dict,
                     onchain: dict,
                     derivatives: dict,
                     multi_tf_aligned: bool = False) -> float:
        """
        Compute a 0‑10 score based on confluence across eight dimensions.
        signal must contain 'direction' and strategy info.
        """
        score = 0.0
        direction = signal.get('direction')
        close = market_data.get('close', [0])[-1]

        # 1. Trend Alignment
        ema200 = ind_values['ema_ribbon']['ema_200'].iloc[-1]
        if direction == 'LONG' and close > ema200:
            score += self.weights['trend_alignment']
        elif direction == 'SHORT' and close < ema200:
            score += self.weights['trend_alignment']

        # 2. Momentum
        rsi = ind_values['rsi'].iloc[-1]
        macd_hist = ind_values['macd']['MACDh_12_26_9'].iloc[-1]
        if direction == 'LONG' and 40 < rsi < 70 and macd_hist > 0:
            score += self.weights['momentum']
        elif direction == 'SHORT' and 60 < rsi < 80 and macd_hist < 0:
            score += self.weights['momentum']

        # 3. Volume Confirmation
        obv = ind_values['obv'].iloc[-1]
        obv_prev = ind_values['obv'].iloc[-2]
        if direction == 'LONG' and obv > obv_prev:
            score += self.weights['volume_confirmation']
        elif direction == 'SHORT' and obv < obv_prev:
            score += self.weights['volume_confirmation']

        # 4. Market Structure (SMC)
        if signal['strategy'] == 'SMC':
            score += self.weights['structure_smc']
        else:
            # partial points if other strategies
            score += self.weights['structure_smc'] * 0.3

        # 5. On‑Chain Support
        mvrv = onchain.get('mvrv_z', 0)
        if direction == 'LONG' and mvrv < 0:
            score += self.weights['onchain_support']
        elif direction == 'SHORT' and mvrv > 5:
            score += self.weights['onchain_support']

        # 6. Volatility Regime
        atr_now = ind_values['atr'].iloc[-1]
        atr_avg = ind_values['atr'].rolling(20).mean().iloc[-1]
        if atr_now > atr_avg:
            score += self.weights['volatility_regime']

        # 7. Sentiment Extreme
        fear_greed = self.sentiment.get_fear_greed()
        if direction == 'LONG' and fear_greed < 25:
            score += self.weights['sentiment']
        elif direction == 'SHORT' and fear_greed > 75:
            score += self.weights['sentiment']

        # 8. Multi‑Timeframe Alignment
        if multi_tf_aligned:
            score += self.weights['multi_tf_alignment']

        return min(score, 10.0)
