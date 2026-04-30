import os
import requests
from loguru import logger
from datetime import datetime, timedelta
import pandas as pd

class SentimentFetcher:
    def __init__(self):
        self.santiment_key = os.getenv('SANTIMENT_API_KEY')
        self.twelve_data_key = os.getenv('TWELVE_DATA_API_KEY')

    def get_fear_greed(self) -> int:
        """
        Fetch Crypto Fear & Greed Index from alternative.me.
        Returns 0-100 integer, or 50 (neutral) on failure.
        """
        try:
            r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10)
            return int(r.json()['data'][0]['value'])
        except Exception as e:
            logger.error(f"Fear & Greed fetch failed: {e}")
            return 50

    def get_social_dominance(self, coin='bitcoin') -> float:
        """
        Fetch social dominance from Santiment (SanAPI) if key exists.
        Free tier supports GraphQL queries.
        Returns a dominance percentage (0-100) or 0 on failure.
        """
        if not self.santiment_key:
            return 0.0
        try:
            query = '''
            {
              socialDominance(slug: "%s", from: "%s", to: "%s", interval: "1d") {
                datetime
                dominance
              }
            }''' % (coin,
                   (datetime.utcnow() - timedelta(days=2)).isoformat(),
                   datetime.utcnow().isoformat())
            r = requests.post(
                'https://api.santiment.net/graphql',
                json={'query': query},
                headers={'Authorization': f'Apikey {self.santiment_key}'},
                timeout=15
            )
            data = r.json()['data']['socialDominance']
            if data:
                return float(data[-1]['dominance'])
        except Exception as e:
            logger.error(f"Social dominance fetch failed: {e}")
        return 0.0

    def get_google_trends(self, keyword='Bitcoin') -> int:
        """
        Attempt to fetch Google Trends interest for a keyword using pytrends.
        If pytrends is not installed or fails, returns 50 (neutral).
        """
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl='en-US', tz=360)
            pytrends.build_payload([keyword], timeframe='now 7-d')
            interest = pytrends.interest_over_time()
            if not interest.empty:
                return int(interest[keyword].iloc[-1])
        except Exception as e:
            logger.error(f"Google Trends fetch failed: {e}")
        return 50

    def get_dxy_spx_correlation(self) -> float:
        """
        Compute rolling 20-day correlation between DXY and SPX daily closes
        using Twelve Data API. Returns a float between -1 and 1, or 0 if missing keys/fails.
        """
        if not self.twelve_data_key:
            return 0.0
        try:
            symbols = ['DXY', 'SPX']
            dfs = {}
            for sym in symbols:
                url = (
                    f'https://api.twelvedata.com/time_series'
                    f'?symbol={sym}&interval=1day&outputsize=30&apikey={self.twelve_data_key}'
                )
                r = requests.get(url, timeout=15)
                data = r.json()['values']
                df = pd.DataFrame(data)
                df['close'] = pd.to_numeric(df['close'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime').set_index('datetime')
                dfs[sym] = df['close']
            merged = pd.DataFrame(dfs)
            corr = merged['DXY'].pct_change().rolling(20).corr(merged['SPX'].pct_change()).iloc[-1]
            return corr if not pd.isna(corr) else 0.0
        except Exception as e:
            logger.error(f"DXY/SPX correlation fetch failed: {e}")
            return 0.0
