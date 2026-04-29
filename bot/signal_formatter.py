from datetime import datetime

def create_embed(signal: dict, score: float, risk_reward: float, risk_params: dict) -> dict:
    direction = signal['direction']
    symbol = signal['symbol']
    tf = signal['timeframe']
    entry = f"{signal['entry_low']:.2f} – {signal['entry_high']:.2f}"
    stop = f"{signal['stop']:.2f}"
    tps = signal['targets']
    tp_str = "\n".join([f"🎯 TP{i+1}: {tp:.2f}" for i, tp in enumerate(tps)])
    conf = score
    rr = risk_reward
    strategies = signal.get('strategy', 'Multiple')
    # Indicator summary
    indicators_used = "EMA ✅ MACD ✅ RSI ✅ OBV ✅"  # placeholder
    regime = "Trending" if score > 7 else "Ranging"
    volatility = "Expanding" if risk_params.get('vol_expanding') else "Normal"

    embed = {
        "title": f"🔔 {symbol} | {direction} | {tf}",
        "color": 0x00ff00 if direction == 'LONG' else 0xff0000,
        "fields": [
            {"name": "📍 Entry Zone", "value": entry, "inline": True},
            {"name": "🛑 Stop Loss", "value": stop, "inline": True},
            {"name": "🎯 Targets", "value": tp_str, "inline": False},
            {"name": "📊 Risk/Reward", "value": f"1:{rr}", "inline": True},
            {"name": "🧠 Confidence", "value": f"{conf:.1f} / 10", "inline": True},
            {"name": "🔀 Strategy", "value": strategies, "inline": False},
            {"name": "Indicators", "value": indicators_used, "inline": False},
            {"name": "Regime", "value": f"{regime} | Volatility {volatility}", "inline": False}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    return embed
