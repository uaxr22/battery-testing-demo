# Battery optimiser testing demo

A small battery trading optimiser (Python + PuLP + HiGHS) with a Pytest suite,
built to practise test automation on Databricks Free Edition.

```
src/battery/optimiser.py     the model: prices + battery limits -> schedule
src/battery/prices.py        PySpark price prep + an API call (mocked in tests)
src/battery/sample_data.py   one realistic GB winter day of prices
tests/                       unit, regression and integration tests
run_tests.py                 Databricks notebook that runs pytest
databricks.yml               bundle definition
resources/                   the battery_tests job (serverless, 2 tasks)
.github/workflows/tests.yml  CI: unit tests on every push
scripts/update_baseline.py   refresh the regression baseline after an intended change
```

Run locally (needs Java 17 for PySpark):

```
pip install -r requirements-dev.txt
pytest -m "not integration" -v
```
