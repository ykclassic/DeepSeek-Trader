import ccxt
import requests
import pandas as pd
from loguru import logger
from datetime import datetime, timedelta
import yaml
import os
from dotenv import load_dotenv

load_dotenv()

class DataFetcher:
    def __init__(self, config):
        self.cfg = config
        self.exchange = ccxt.binance({
            'apiKey': os.getenv('EXCHANGE_API_KEY'),
            'secret': os.getenv('EXCHANGE_SECRET'),
            'enableRateLimit': True,
        })
        self.glassnode_key = os.getenv('GLASSNODE_API_KEY')
        self.coinglass_key = os.getenv('COINGLASS_API_KEY')

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 500):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.error(f"OHLCV fetch failed: {e}")
            return pd.DataFrame()

    def fetch_glassnode_metric(self, metric: str, asset: str = 'BTC'):
        # Glassnode free API V1
        url = f"https://api.glassnode.com/v1/metrics/{metric}"
        params = {'a': asset, 'api_key': self.glassnode_key, 'f': 'json'}
        try:
            r = requests.get(url, params=params, timeout=10)
            return r.json()
        except:
            return []

    def fetch_coinglass_data(self, endpoint: str):
        # Coinglass API (free tier)
        url = f"https://open-api-v3.coinglass.com/api/{endpoint}"
        headers = {'coinglassSecret': self.coinglass_key}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            return r.json() if r.ok else {}
        except:
            return {}

    def get_onchain_bundle(self):
        # Combine relevant metrics
        mvrv = self.fetch_glassnode_metric('market/mvrv_z_score')
        puell = self.fetch_glassnode_metric('miner/puell_multiple')
        netflow = self.fetch_glassnode_metric('distribution/exchange_net_position_change')
        return {
            'mvrv_z': mvrv,
            'puell': puell,
            'netflow': netflow
        }
