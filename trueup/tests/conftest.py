"""Shared test fixtures for TrueUp test suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.data_generator import build_dataset, write_dataset
from src.deterministic_matcher import load_sources


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    write_dataset(build_dataset(), data_dir)
    return {"records": load_sources(data_dir), "dir": data_dir}


@pytest.fixture(scope="module")
def generated_data_dir(generated):
    return generated["dir"]


@pytest.fixture(scope="module")
def gt_path(generated_data_dir):
    return generated_data_dir
