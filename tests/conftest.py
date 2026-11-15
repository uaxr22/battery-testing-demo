"""Shared fixtures. Pytest finds this file automatically."""
import os

import pytest

from battery.optimiser import Battery
from battery.sample_data import SAMPLE_DAY_PRICES

ON_DATABRICKS = "DATABRICKS_RUNTIME_VERSION" in os.environ


@pytest.fixture(scope="session")
def spark():
    """One Spark session for the whole test run.

    On Databricks we reuse the workspace's Spark session.
    Anywhere else (laptop, GitHub Actions) we start a small local one.
    """
    from pyspark.sql import SparkSession

    if ON_DATABRICKS:
        yield SparkSession.builder.getOrCreate()
        return
    session = (
        SparkSession.builder.master("local[1]")
        .appName("battery-unit-tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def battery():
    """A 2-hour battery, like SSE's Ferrybridge site but smaller numbers."""
    return Battery(power_mw=100, energy_mwh=200, efficiency=0.9, initial_soc_mwh=0)


@pytest.fixture
def sample_prices():
    """A typical GB winter day: cheap overnight, peak at 17:00-19:00 (GBP/MWh)."""
    return [float(p) for p in SAMPLE_DAY_PRICES]
