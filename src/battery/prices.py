"""Getting market prices ready for the optimiser.

Raw prices arrive every 15 minutes. The optimiser works in GB
settlement periods of 30 minutes, so we average them up.
"""
from __future__ import annotations

import requests
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

PRICE_API_URL = "https://prices.example.com/api/day-ahead"


def to_half_hourly(df: DataFrame) -> DataFrame:
    """Average 15-minute prices into 30-minute settlement periods.

    Input columns:  ts (string or timestamp), price (double)
    Output columns: period_start (timestamp), avg_price (double)
    """
    ts = F.to_timestamp("ts")
    period_start = F.timestamp_seconds(F.floor(F.unix_timestamp(ts) / 1800) * 1800)
    return (
        df.withColumn("period_start", period_start)
        .groupBy("period_start")
        .agg(F.round(F.avg("price"), 4).alias("avg_price"))
        .orderBy("period_start")
    )


def count_duplicate_periods(df: DataFrame, key: str = "period_start") -> int:
    """How many period keys appear more than once (should be 0)."""
    return df.groupBy(key).count().filter("count > 1").count()


def fetch_day_ahead_prices(date: str, url: str = PRICE_API_URL) -> list[float]:
    """Download 48 half-hourly day-ahead prices for one date from an API."""
    response = requests.get(url, params={"date": date}, timeout=10)
    response.raise_for_status()
    prices = response.json()["prices"]
    if len(prices) not in (46, 48, 50):  # 46/50 on clock-change days
        raise ValueError(f"expected 46, 48 or 50 prices, got {len(prices)}")
    return [float(p) for p in prices]
