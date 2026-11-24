#!/usr/bin/env python3
"""
Benchmark: Nearest-Neighbor Heuristic vs OR-Tools Guided Local Search
Run: python benchmarks/compare_algorithms.py
"""

import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.solver import solve_tsp

EARTH_RADIUS = 6_371_000
SPEED_MPS = 50.0 * (1000 / 3600)


def nearest_neighbor(matrix: list[list[int]], start: int = 0) -> list[int]:
    unvisited = set(range(len(matrix))) - {start}
    route, current = [start], start
    while unvisited:
        nearest = min(unvisited, key=lambda j: matrix[current][j])
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    route.append(start)
    return route


def route_cost(matrix: list[list[int]], route: list[int]) -> int:
    return sum(matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))


def random_matrix(n: int, seed: int = 42) -> list[list[int]]:
    rng = random.Random(seed)
    coords = [(rng.uniform(18.0, 28.0), rng.uniform(72.0, 88.0)) for _ in range(n)]

    def haversine(a: tuple[float, float], b: tuple[float, float]) -> int:
        p1, p2, dlat, dlng = math.radians(a[0]), math.radians(b[0]), math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
        h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
        return int((2 * EARTH_RADIUS * math.asin(math.sqrt(h))) / SPEED_MPS)

    return [[0 if i == j else haversine(coords[i], coords[j]) for j in range(n)] for i in range(n)]


def run_benchmark(stop_counts: list[int] = [5, 10, 15, 20], seed: int = 42):
    header = f"\n{'Stops':>6}  {'NN Time (s)':>12}  {'ORT Time (s)':>13}  {'NN Cost (s)':>12}  {'ORT Cost (s)':>13}  {'Improvement':>12}"
    print(header)
    print("─" * len(header))

    for n in stop_counts:
        matrix = random_matrix(n, seed=seed)

        t0 = time.perf_counter()
        nn_r = nearest_neighbor(matrix, start=0)
        nn_time = time.perf_counter() - t0
        nn_c = route_cost(matrix, nn_r)

        t0 = time.perf_counter()
        ort_r = solve_tsp(matrix, start_index=0, end_index=0)
        ort_time = time.perf_counter() - t0
        ort_c = route_cost(matrix, ort_r)

        imp = ((nn_c - ort_c) / nn_c * 100) if nn_c > 0 else 0.0
        print(f"{n:>6}  {nn_time:>12.4f}  {ort_time:>13.4f}  {nn_c:>12,d}  {ort_c:>13,d}  {imp:>11.1f}%")

    print("\nNotes: Costs represent total travel time (seconds); lower is better.\n")


if __name__ == "__main__":
    run_benchmark()
