# Databricks notebook source
# MAGIC %md
# MAGIC # Run the battery optimiser test suite
# MAGIC Runs Pytest on Databricks serverless compute.
# MAGIC * Run it by hand: leave **marker** blank to run every test.
# MAGIC * The `battery_tests` job runs it twice: unit tests first, then integration tests.

# COMMAND ----------

# MAGIC %pip install -q pulp==2.9.0 highspy pytest pytest-mock

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("marker", "", "Pytest -m expression (blank = all tests)")
marker = dbutils.widgets.get("marker").strip()

# COMMAND ----------

import os
import sys

import pytest

# The workspace file system is read-only for Python's cache files.
sys.dont_write_bytecode = True

# This notebook sits in the project root, so the working directory is the root
# and pytest.ini (testpaths, pythonpath = src, markers) is picked up.
print("Running tests from:", os.getcwd())

args = ["-v", "-p", "no:cacheprovider", "--junitxml=/tmp/test-results.xml"]
if marker:
    args += ["-m", marker]

exit_code = pytest.main(args)
print("pytest exit code:", int(exit_code))

# COMMAND ----------

# Exit code 5 = no tests matched the marker; treat that as a pass.
# Any other non-zero code fails this cell, so the job run shows as FAILED.
assert int(exit_code) in (0, 5), "Some tests failed - see the output above."
