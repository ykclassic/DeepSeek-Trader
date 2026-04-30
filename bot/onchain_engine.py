from loguru import logger
from bot.data_fetcher import DataFetcher

class OnchainEngine:
    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher

    def get_full_onchain(self, asset='BTC') -> dict:
        """
        Aggregates all on‑chain metrics into a single dictionary.
        Returns None values replaced by zeros so scoring never crashes.
        """
        data = {}
        try:
            data['mvrv_z'] = self.fetcher.get_mvrv_z(asset) or 0
            data['puell'] = self.fetcher.get_puell_multiple(asset) or 0
            data['sopr'] = self.fetcher.get_sopr(asset) or 0
            data['netflow'] = self.fetcher.get_exchange_netflow(asset) or 0
            data['active_addresses'] = self.fetcher.get_active_addresses(asset) or 0
            data['tx_volume'] = self.fetcher.get_transaction_volume(asset) or 0
            data['btc_dominance'] = self.fetcher.get_btc_dominance() or 0
            data['ssr'] = self.fetcher.get_ssr() or 0
        except Exception as e:
            logger.error(f"On‑chain data error: {e}")
        return data

    def get_derivatives(self, symbol='BTC') -> dict:
        d = {}
        try:
            d['funding_rate'] = self.fetcher.get_funding_rate(symbol)
            d['open_interest'] = self.fetcher.get_open_interest(symbol)
            d['long_short_ratio'] = self.fetcher.get_long_short_ratio(symbol)
        except Exception as e:
            logger.error(f"Derivatives data error: {e}")
        return d

    def get_liquidation_levels(self, symbol='BTC') -> list:
        return self.fetcher.get_liquidation_heatmap(symbol)
