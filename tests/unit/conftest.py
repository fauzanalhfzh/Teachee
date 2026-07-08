import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    yield


@pytest.fixture(autouse=True)
def clean_database():
    yield
