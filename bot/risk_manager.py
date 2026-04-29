import json
import os
from datetime import datetime, timedelta
from loguru import logger

class RiskManager:
    def __init__(self, config):
        self.cfg = config['risk']
        self.state_file = "state/risk_state.json"
        self.state = self._load_state()
        self.current_positions = []

    def _load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {'daily_pnl': 0.0, 'weekly_pnl': 0.0, 'consecutive_losses': 0,
                'last_trade_date': None, 'kill_switch': False, 'paused_until': None}

    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)

    def check_kill_switch(self):
        if self.state.get('kill_switch'): return True
        if self.state.get('paused_until'):
            if datetime.now() < datetime.fromisoformat(self.state['paused_until']):
                return True
        return False

    def can_open_trade(self, signal):
        # Max correlated trades
        correlated = [p for p in self.current_positions if p['symbol'] == signal['symbol']]
        if len(correlated) >= self.cfg['max_correlated_trades']:
            return False
        # Risk per trade check (simulated account balance)
        # Here we assume fixed balance; real implementation uses exchange fetch
        return True

    def size_position(self, entry, stop, balance=1000):
        risk_amount = balance * self.cfg['max_risk_per_trade']
        atr = stop  # simplified: stop distance from signal
        if atr <= 0: return 0
        position_size = risk_amount / atr
        return round(position_size, 6)

    def update_state(self, trade_result: dict):
        # trade_result: {'pnl_percent': +0.5, 'win': True}
        pnl = trade_result['pnl_percent']
        today = datetime.now().date().isoformat()
        if self.state['last_trade_date'] != today:
            self.state['daily_pnl'] = 0.0
            self.state['last_trade_date'] = today
        self.state['daily_pnl'] += pnl
        # weekly drawdown monitor
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).date().isoformat()
        if 'weekly_pnl_start' not in self.state or self.state['week_start'] != week_start:
            self.state['weekly_pnl'] = 0.0
            self.state['week_start'] = week_start
        self.state['weekly_pnl'] += pnl
        if trade_result['win']:
            self.state['consecutive_losses'] = 0
        else:
            self.state['consecutive_losses'] += 1
        # Circuit breakers
        if self.state['daily_pnl'] <= -self.cfg['daily_loss_limit']:
            self.state['paused_until'] = (datetime.now() + timedelta(hours=24)).isoformat()
            logger.warning("Daily loss limit hit. Pausing for 24h.")
        if self.state['weekly_pnl'] <= -self.cfg['weekly_dd_limit']:
            self.state['kill_switch'] = True
            logger.error("Weekly drawdown limit breached. Kill switch activated.")
        if self.state['consecutive_losses'] >= self.cfg['consecutive_loss_cap']:
            self.state['paused_until'] = (datetime.now() + timedelta(hours=4)).isoformat()
            logger.warning("3 consecutive losses. Paused.")
        self._save_state()
