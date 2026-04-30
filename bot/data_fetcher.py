import ccxt
import requests
import pandas as pd
from loguru import logger
import yaml
import os
from dotenv import load_dotenv

load_dotenv()

class DataFetcher:
    def __init__(self, config):
        self.cfg = config
        exchange_name = config.get('exchange', {}).get('name', 'xt').lower()
        use_keys = config.get('exchange', {}).get('use_api_keys', False)

        # Get the CCXT exchange class
        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            logger.error(f"Exchange '{exchange_name}' not found in CCXT. Falling back to xt.")
            exchange_class = ccxt.xt

        # Build exchange instance – public data works without API keys
        exchange_kwargs = {'enableRateLimit': True}
        if use_keys:
            exchange_kwargs['apiKey'] = os.getenv('EXCHANGE_API_KEY', '')
            exchange_kwargs['secret'] = os.getenv('EXCHANGE_SECRET', '')
            logger.info(f"Using API keys for {exchange_name}")
        else:
            logger.info(f"Using {exchange_name} without API keys (public data only)")

        self.exchange = exchange_class(exchange_kwargs)

        # Other optional API keys
        self.glassnode_key = os.getenv('GLASSNODE_API_KEY')
        self.coinglass_key = os.getenv('COINGLASS_API_KEY')

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 500) -> pd.DataFrame:
        """Fetch OHLCV candlestick data from the exchange."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.error(f"OHLCV fetch failed for {symbol} {timeframe}: {e}")
            return pd.DataFrame()

    # ---------- Glassnode (on‑chain data) ----------
    def _glassnode_req(self, endpoint: str, asset: str = 'BTC', since: int = None) -> list:
        url = f"https://api.glassnode.com/v1/metrics/{endpoint}"
        params = {'a': asset, 'api_key': self.glassnode_key, 'f': 'json'}
        if since:
            params['s'] = since
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.ok:
                return r.json()
            logger.warning(f"Glassnode {endpoint}: {r.status_code}")
            return []
        except Exception as e:
            logger.error(f"Glassnode request failed: {e}")
            return []

    def get_mvrv_z(self, asset='BTC') -> float:
        data = self._glassnode_req('market/mvrv_z_score', asset)
        return float(data[-1]['v']) if data else None

    def get_puell_multiple(self, asset='BTC') -> float:
        data = self._glassnode_req('miner/puell_multiple', asset)
        return float(data[-1]['v']) if data else None

    def get_sopr(self, asset='BTC') -> float:
        data = self._glassnode_req('indicators/sopr', asset)
        return float(data[-1]['v']) if data else None

    def get_exchange_netflow(self, asset='BTC') -> float:
        data = self._glassnode_req('distribution/exchange_net_position_change', asset)
        return float(data[-1]['v']) if data else None

    def get_active_addresses(self, asset='BTC') -> float:
        data = self._glassnode_req('transactions/active_addresses', asset)
        return float(data[-1]['v']) if data else None

    def get_transaction_volume(self, asset='BTC') -> float:
        data = self._glassnode_req('transactions/volume', asset)
        return float(data[-1]['v']) if data else None

    def get_btc_dominance(self) -> float:
        data = self._glassnode_req('market/btc_dominance')
        return float(data[-1]['v']) if data else None

    def get_ssr(self) -> float:
        data = self._glassnode_req('stablecoin/ssr')
        return float(data[-1]['v']) if data else None

    # ---------- Coinglass (derivatives + liquidations) ----------
    def _coinglass_req(self, endpoint: str) -> dict:
        url = f"https://open-api-v3.coinglass.com/api/{endpoint}"
        headers = {'coinglassSecret': self.coinglass_key}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.ok:
                return r.json()
            logger.warning(f"Coinglass {endpoint}: {r.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Coinglass request failed: {e}")
            return {}

    def get_funding_rate(self, symbol='BTC') -> float:
        resp = self._coinglass_req(f'futures/fundingRate?symbol={symbol}')
        try:
            return float(resp['data'][-1]['fundingRate'])
        except:
            return 0.0

    def get_open_interest(self, symbol='BTC') -> float:
        resp = self._coinglass_req(f'futures/openInterest?symbol={symbol}')
        try:
            return float(resp['data'][-1]['openInterest'])
        except:
            return 0.0

    def get_long_short_ratio(self, symbol='BTC') -> float:
        resp = self._coinglass_req(f'futures/longShortRatio?symbol={symbol}')
        try:
            return float(resp['data'][-1]['longShortRatio'])
        except:
            return 1.0

    def get_liquidation_heatmap(self, symbol='BTC') -> list:
        resp = self._coinglass_req(f'futures/liquidation/detail?symbol={symbol}&timeType=4')
        if 'data' in resp:
            return resp['data']
        return []

    def get_fear_greed_index(self) -> int:
        try:
            r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10)
            return int(r.json()['data'][0]['value'])
        except:
            return 50
