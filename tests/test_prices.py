"""Tests for price preparation: PySpark transforms and an API call."""
import pytest
import requests

from battery import prices as price_module
from battery.prices import count_duplicate_periods, fetch_day_ahead_prices, to_half_hourly


# ---------- PySpark transformation (uses the session-scoped spark fixture) ----------

def test_to_half_hourly_averages_two_quarter_hours(spark):
    raw = spark.createDataFrame(
        [("2026-11-01 00:00:00", 40.0), ("2026-11-01 00:15:00", 60.0),
         ("2026-11-01 00:30:00", 70.0), ("2026-11-01 00:45:00", 90.0)],
        ["ts", "price"],
    )
    rows = to_half_hourly(raw).collect()
    assert [r.avg_price for r in rows] == [50.0, 80.0]
    assert len(rows) == 2


def test_to_half_hourly_keeps_negative_prices(spark):
    raw = spark.createDataFrame(
        [("2026-11-01 03:00:00", -10.0), ("2026-11-01 03:15:00", -30.0)], ["ts", "price"]
    )
    assert to_half_hourly(raw).first().avg_price == -20.0


def test_output_schema(spark):
    raw = spark.createDataFrame([("2026-11-01 00:00:00", 40.0)], ["ts", "price"])
    out = to_half_hourly(raw)
    assert out.columns == ["period_start", "avg_price"]
    assert dict(out.dtypes)["period_start"] == "timestamp"


def test_full_day_gives_48_periods_and_no_duplicates(spark):
    from datetime import datetime, timedelta

    start = datetime(2026, 11, 1)
    rows = [((start + timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S"), 50.0)
            for i in range(96)]
    out = to_half_hourly(spark.createDataFrame(rows, ["ts", "price"]))
    assert out.count() == 48
    assert count_duplicate_periods(out) == 0


def test_duplicate_check_finds_duplicates(spark):
    df = spark.createDataFrame([("a",), ("a",), ("b",)], ["period_start"])
    assert count_duplicate_periods(df) == 1


# ---------- Mocking: no real network call ----------

def test_fetch_prices_parses_api_response(mocker):
    fake_get = mocker.patch("battery.prices.requests.get")
    fake_get.return_value.json.return_value = {"prices": [50] * 48}

    prices = fetch_day_ahead_prices("2026-11-01")

    assert prices == [50.0] * 48
    fake_get.assert_called_once_with(
        price_module.PRICE_API_URL, params={"date": "2026-11-01"}, timeout=10
    )


def test_fetch_prices_rejects_wrong_number_of_periods(mocker):
    fake_get = mocker.patch("battery.prices.requests.get")
    fake_get.return_value.json.return_value = {"prices": [50] * 47}
    with pytest.raises(ValueError, match="got 47"):
        fetch_day_ahead_prices("2026-11-01")


def test_fetch_prices_raises_when_api_is_down(mocker):
    fake_get = mocker.patch("battery.prices.requests.get")
    fake_get.return_value.raise_for_status.side_effect = requests.HTTPError("503")
    with pytest.raises(requests.HTTPError):
        fetch_day_ahead_prices("2026-11-01")
