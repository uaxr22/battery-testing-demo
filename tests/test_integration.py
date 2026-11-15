"""Integration test: real Delta table on Databricks -> optimiser -> schedule table.

Marked `integration` and skipped automatically when not on Databricks,
so it never runs on a laptop or in GitHub Actions.
"""
import os
import uuid

import pytest

from battery.optimiser import optimise

ON_DATABRICKS = "DATABRICKS_RUNTIME_VERSION" in os.environ

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not ON_DATABRICKS, reason="needs a Databricks workspace"),
]

SCHEMA = "workspace.default"   # exists in every Databricks Free Edition workspace


@pytest.fixture
def prices_table(spark, sample_prices):
    """Write the sample day to a temporary Delta table, drop it afterwards."""
    name = f"{SCHEMA}.test_prices_{uuid.uuid4().hex[:8]}"
    rows = [(i + 1, p) for i, p in enumerate(sample_prices)]
    spark.createDataFrame(rows, "settlement_period INT, price DOUBLE") \
        .write.format("delta").mode("overwrite").saveAsTable(name)
    yield name
    spark.sql(f"DROP TABLE IF EXISTS {name}")


def test_optimiser_runs_on_delta_table(spark, prices_table, battery):
    df = spark.table(prices_table).orderBy("settlement_period")
    prices = [r.price for r in df.collect()]
    assert len(prices) == 48

    schedule = optimise(prices, battery)

    out_name = prices_table.replace("test_prices_", "test_schedule_")
    try:
        spark.createDataFrame(
            [(p.index + 1, p.action, p.charge_mw, p.discharge_mw, p.soc_mwh)
             for p in schedule.periods],
            "settlement_period INT, action STRING, charge_mw DOUBLE, "
            "discharge_mw DOUBLE, soc_mwh DOUBLE",
        ).write.format("delta").mode("overwrite").saveAsTable(out_name)

        written = spark.table(out_name)
        assert written.count() == 48
        assert written.filter("soc_mwh < 0 OR soc_mwh > 200.0001").count() == 0
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {out_name}")
