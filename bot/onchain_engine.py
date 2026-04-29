from loguru import logger

class OnchainEngine:
    def __init__(self, data_fetcher, config):
        self.fetcher = data_fetcher
        self.cfg = config

    def get_onchain_signals(self):
        bundle = self.fetcher.get_onchain_bundle()
        signals = {}
        # MVRV Z-Score
        try:
            mvrv = bundle['mvrv_z'][-1]['v'] if bundle['mvrv_z'] else 0
            signals['mvrv_z'] = float(mvrv)
        except: signals['mvrv_z'] = 0
        # Puell Multiple
        try:
            puell = bundle['puell'][-1]['v'] if bundle['puell'] else 0
            signals['puell'] = float(puell)
        except: signals['puell'] = 0
        # Netflow (negative = outflow)
        try:
            nf = bundle['netflow'][-1]['v'] if bundle['netflow'] else 0
            signals['netflow'] = float(nf)
        except: signals['netflow'] = 0
        # Funding rate from Coinglass (placeholder)
        signals['funding_rate'] = 0.0
        signals['open_interest'] = 0.0
        signals['long_short_ratio'] = 1.0
        cog = self.fetcher.fetch_coinglass_data('futures/openInterest?symbol=BTC')
        if cog and 'data' in cog:
            oi_list = cog['data']
            if oi_list: signals['open_interest'] = oi_list[-1]['openInterest']
        return signals
