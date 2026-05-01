import ccxt
import requests
import pandas as pd
from loguru import logger
import yaml
import os
from dotenv import load_dotenv

load_dotenv()


class DataFetcher:
    """
    Unified data layer.
    OHLCV   → CCXT (currently XT, configurable)
    On‑chain → BGeometrics free Bitcoin Data API
    Derivatives → Coinglass (optional)
    """

    def __init__(self, config):
        self.cfg = config

        # ── CCXT exchange ────────────────────────────────────────
        exchange_name = config.get("exchange", {}).get("name", "xt").lower()
        use_keys = config.get("exchange", {}).get("use_api_keys", False)

        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            logger.error(
                f"Exchange '{exchange_name}' not found in CCXT. Falling back to xt."
            )
            exchange_class = ccxt.xt

        exchange_kwargs = {"enableRateLimit": True}
        if use_keys:
            exchange_kwargs["apiKey"] = os.getenv("EXCHANGE_API_KEY", "")
            exchange_kwargs["secret"] = os.getenv("EXCHANGE_SECRET", "")
            logger.info(f"Using API keys for {exchange_name}")
        else:
            logger.info(f"Using {exchange_name} without API keys (public data only)")

        self.exchange = exchange_class(exchange_kwargs)

        # ── BGeometrics (on‑chain) ───────────────────────────────
        self.bgeometrics_token = os.getenv("BGEOMETRICS_API_KEY")

        # ── Coinglass (derivatives) ──────────────────────────────
        self.coinglass_key = os.getenv("COINGLASS_API_KEY")

    # =================================================================
    #  OHLCV (exchange)
    # =================================================================
    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 500
    ) -> pd.DataFrame:
        """Returns a DataFrame with columns open/high/low/close/volume."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception as e:
            logger.error(f"OHLCV fetch failed for {symbol} {timeframe}: {e}")
            return pd.DataFrame()

    # =================================================================
    #  BGeometrics – on‑chain Bitcoin metrics
    # =================================================================
    BGEOMETRICS_BASE = "https://bitcoin-data.com/v1"

    def _bgeometrics_req(self, endpoint: str) -> list | dict | None:
        """
        Generic GET request to the BGeometrics Bitcoin Data API.

        Authentication is passed as a query parameter, as per their docs:
            GET /v1/endpoint?token=YOUR_TOKEN
        """
        if not self.bgeometrics_token:
            logger.warning("BGeometrics token not set – on‑chain data unavailable.")
            return None

        url = f"{self.BGEOMETRICS_BASE}/{endpoint}"
        params = {"token": self.bgeometrics_token}

        try:
            r = requests.get(url, params=params, timeout=15)
            if r.ok:
                return r.json()
            logger.warning(f"BGeometrics {endpoint}: {r.status_code} – {r.text}")
            return None
        except Exception as e:
            logger.error(f"BGeometrics request failed ({endpoint}): {e}")
            return None

    def get_mvrv_z(self, asset: str = "BTC") -> float | None:
        data = self._bgeometrics_req("mvrv-z-score")
        if isinstance(data, list) and data:
            return float(data[-1].get("v", data[-1].get("value", 0)))
        if isinstance(data, dict):
            return float(data.get("v", data.get("value", 0)))
        return None

    def get_puell_multiple(self, asset: str = "BTC") -> float | None:
        data = self._bgeometrics_req("puell-multiple")
        if isinstance(data, list) and data:
            return float(data[-1].get("v", data[-1].get("value", 0)))
        if isinstance(data, dict):
            return float(data.get("v", data.get("value", 0)))
        return None

    def get_sopr(self, asset: str = "BTC") -> float | None:
        data = self._bgeometrics_req("sopr")
        if isinstance(data, list) and data:
            return float(data[-1].get("v", data[-1].get("value", 0)))
        if isinstance(data, dict):
            return float(data.get("v", data.get("value", 0)))
        return None

    def get_exchange_netflow(self, asset: str = "BTC") -> float | None:
        data = self._bgeometrics_req("exchange-netflow-btc")
        if isinstance(data, list) and data:
            return float(data[-1].get("v", data[-1].get("value", 0)))
        if isinstance(data, dict):
            return float(data.get("v", data.get("value", 0)))
        return None

    def get_active_addresses(self, asset: str = "BTC") -> float | None:
        data = self._bgeometrics_req("active-addresses")
        if isinstance(data, list) and data:
            return float(data[-1].get("v", data[-1].get("value", 0)))
        if isinstance(data, dict):
            return float(data.get("v", data.get("value", 0)))
        return None

    def get_transaction_volume(self, asset: str = "BTC") -> float | None:
        data = self._bgeometrics_req("transaction-volume")
        if isinstance(data, list) and data:
            return float(data[-1].get("v", data[-1].get("value", 0)))
        if isinstance(data, dict):
            return float(data.get("v", data.get("value", 0)))
        return None

    def get_btc_dominance(self) -> float | None:
        return None

    def get_ssr(self) -> float | None:
        return None

    # =================================================================
    #  Coinglass – derivatives & liquidations (unchanged)
    # =================================================================
    def _coinglass_req(self, endpoint: str) -> dict:
        url = f"https://open-api-v3.coinglass.com/api/{endpoint}"
        headers = {"coinglassSecret": self.coinglass_key}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.ok:
                return r.json()
            logger.warning(f"Coinglass {endpoint}: {r.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Coinglass request failed: {e}")
            return {}

    def get_funding_rate(self, symbol: str = "BTC") -> float:
        resp = self._coinglass_req(f"futures/fundingRate?symbol={symbol}")
        try:
            return float(resp["data"][-1]["fundingRate"])
        except Exception:
            return 0.0

    def get_open_interest(self, symbol: str = "BTC") -> float:
        resp = self._coinglass_req(f"futures/openInterest?symbol={symbol}")
        try:
            return float(resp["data"][-1]["openInterest"])
        except Exception:
            return 0.0

    def get_long_short_ratio(self, symbol: str = "BTC") -> float:
        resp = self._coinglass_req(f"futures/longShortRatio?symbol={symbol}")
        try:
            return float(resp["data"][-1]["longShortRatio"])
        except Exception:
            return 1.0

    def get_liquidation_heatmap(self, symbol: str = "BTC") -> list:
        resp = self._coinglass_req(
            f"futures/liquidation/detail?symbol={symbol}&timeType=4"
        )
        if "data" in resp:
            return resp["data"]
        return []

    def get_fear_greed_index(self) -> int:
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
            return int(r.json()["data"][0]["value"])
        except Exception:
            return 50
