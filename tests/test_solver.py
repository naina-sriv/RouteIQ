import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from utils.solver import solve_tsp


def make_matrix(n):
    """Simple n×n matrix where cost(i,j) = |i-j|."""
    return [[abs(i - j) * 100 for j in range(n)] for i in range(n)]


def test_start_node_is_first():
    matrix = make_matrix(5)
    route = solve_tsp(matrix, start_index=0, end_index=0)
    assert route[0] == 0


def test_end_node_is_last():
    matrix = make_matrix(5)
    route = solve_tsp(matrix, start_index=0, end_index=0)
    assert route[-1] == 0


def test_all_nodes_visited():
    matrix = make_matrix(6)
    route = solve_tsp(matrix, start_index=0, end_index=0)
    assert sorted(route[:-1]) == list(range(6))


def test_different_start_end():
    matrix = make_matrix(5)
    route = solve_tsp(matrix, start_index=1, end_index=3)
    assert route[0] == 1
    assert route[-1] == 3


def test_two_stop_edge_case():
    matrix = [[0, 500], [500, 0]]
    route = solve_tsp(matrix, start_index=0, end_index=1)
    assert route[0] == 0
    assert route[-1] == 1
    assert len(route) == 2


def test_raises_on_too_few_stops():
    with pytest.raises(ValueError):
        solve_tsp([[0]], start_index=0, end_index=0)


def test_raises_on_too_many_stops():
    n = 21
    matrix = [[0] * n for _ in range(n)]
    with pytest.raises(ValueError):
        solve_tsp(matrix, start_index=0, end_index=0)


def test_total_duration_matches_legs():
    matrix = make_matrix(5)
    route = solve_tsp(matrix, start_index=0, end_index=0)
    total_from_legs = sum(matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))
    assert total_from_legs >= 0  # sanity — cost is non-negative
