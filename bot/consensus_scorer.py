import numpy as np
import pandas as pd
from loguru import logger

class ConsensusScorer:
    def __init__(self, config):
        self.weights = config['consensus_scoring']['weights']
        self.min_score = config['consensus_scoring']['minimum_fire_score']
        self.high_conv = config['consensus_scoring']['high_conviction_threshold']

    def score_signal(self, signal: dict, ind_values: dict, market_data: dict):
        """
        Compute a 0-10 score based on confluence dimensions.
        signal: must have 'direction' and strategy info.
        ind_values: computed indicator dict (from IndicatorEngine).
        market_data: additional context like on-chain data.
        """
        score = 0.0
        # Trend Alignment
        if signal.get('direction') == 'LONG':
            ema200 = ind_values['ema_ribbon']['ema_200'].iloc[-1]
            close = market_data['close'][-1]
            if close > ema200: score += self.weights['trend_alignment']
        else:
            # SHORT: check bearish trend
            score += self.weights['trend_alignment'] * 0.5  # simplified

        # Momentum
        rsi = ind_values['rsi'].iloc[-1]
        macd_hist = ind_values['macd']['MACDh_12_26_9'].iloc[-1]
        if signal['direction'] == 'LONG' and 40 < rsi < 70 and macd_hist > 0:
            score += self.weights['momentum']
        elif signal['direction'] == 'SHORT' and rsi > 60:
            score += self.weights['momentum'] * 0.5

        # Volume Confirmation
        if 'obv' in ind_values:
            obv = ind_values['obv'].iloc[-1]
            obv_prev = ind_values['obv'].iloc[-2]
            if (signal['direction'] == 'LONG' and obv > obv_prev) or \
               (signal['direction'] == 'SHORT' and obv < obv_prev):
                score += self.weights['volume_confirmation']

        # SMC structure (already considered in strategy)
        if signal['strategy'] == 'SMC':
            score += self.weights['structure_smc']
        else:
            # partial if market structure aligned
            score += self.weights['structure_smc'] * 0.3

        # On-chain support
        onchain = market_data.get('onchain', {})
        if signal['direction'] == 'LONG' and onchain.get('mvrv_z', 1) < 0:
            score += self.weights['onchain_support']
        elif signal['direction'] == 'SHORT' and onchain.get('mvrv_z', 1) > 5:
            score += self.weights['onchain_support']

        # Volatility regime – check if ATR is above its 20-period average
        atr_now = ind_values['atr'].iloc[-1]
        atr_avg = ind_values['atr'].rolling(20).mean().iloc[-1]
        if atr_now > atr_avg:
            score += self.weights['volatility_regime']  # expansion favorable

        # Sentiment
        fear_greed = market_data.get('fear_greed', 50)
        if (signal['direction'] == 'LONG' and fear_greed < 25) or \
           (signal['direction'] == 'SHORT' and fear_greed > 75):
            score += self.weights['sentiment']

        # Multi-TF alignment (placeholder: assume 1 if other TFs same direction)
        score += self.weights['multi_tf_alignment'] * 0.8  # we'll later check multi-TF

        return min(score, 10.0)
