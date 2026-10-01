"""Helpers that write tiny files in the same formats the solver and the C++ suite produce."""
import numpy as np
import pytest


def write_solver_bin(path, values):
    """Same layout as fileLib::write_file: uint32 byte size, then the raw values."""
    values = np.ascontiguousarray(values)
    with open(path, "wb") as f:
        np.array([values.nbytes], dtype=np.uint32).tofile(f)
        values.tofile(f)


@pytest.fixture
def bin_dir(tmp_path):
    """Two rank groups at step 1600: rank 0 has 2 particles, rank 1 has 1. c_ref = 100."""
    ids = {0: np.array([10001, 20003], np.int32), 1: np.array([30002], np.int32)}
    pos = {0: np.array([[1, 2, 3], [4, 5, 6]], np.float32), 1: np.array([[7, 8, 9]], np.float32)}
    # SGS in m/s; uvw in lattice units and already resolved + SGS (flg_particle = 1)
    sgs = {0: np.array([[0.1, 0.2, 0.3], [0.0, 0.0, 0.0]], np.float32), 1: np.array([[0.5, 0.5, 0.5]], np.float32)}
    resolved = {0: np.array([[2.0, 0.0, 0.0], [3.0, 1.0, -1.0]], np.float32), 1: np.array([[1.0, 1.0, 1.0]], np.float32)}
    for r in (0, 1):
        write_solver_bin(tmp_path / f"index{r}-1600.bin", ids[r])
        write_solver_bin(tmp_path / f"position{r}-1600.bin", pos[r])
        write_solver_bin(tmp_path / f"uvw_sgs{r}-1600.bin", sgs[r])
        write_solver_bin(tmp_path / f"uvw{r}-1600.bin", ((resolved[r] + sgs[r]) / 100.0).astype(np.float32))
    return tmp_path
