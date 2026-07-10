#!/usr/bin/env python3
"""
Benchmark: nearest-neighbor heuristic vs OR-Tools Guided Local Search
Run: python benchmarks/compare_algorithms.py
"""
import sys
import math
import random
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.solver import solve_tsp






def nearest_neighbor(matrix: list[list[int]], start: int = 0) -> list[int]:
    n = len(matrix)
    unvisited = set(range(n)) - {start}
    route = [start]
    current = start
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
    points = [(rng.uniform(18, 28), rng.uniform(72, 88)) for _ in range(n)]


    def haversine(a, b):
        R = 6371000
        phi1, phi2 = math.radians(a[0]), math.radians(b[0])
        dphi = math.radians(b[0] - a[0])
        dl = math.radians(b[1] - a[1])
        h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
        return int(2 * R * math.asin(math.sqrt(h)) / (50_000 / 3600))

    return [[haversine(points[i], points[j]) if i != j else 0 for j in range(n)] for i in range(n)]


def benchmark(stop_counts: list[int] = [5, 10, 15, 20], seed: int = 42):
    print(f"\n{'Stops':>6}  {'NN (s)':>10}  {'OR-Tools (s)':>12}  {'NN time':>10}  {'OR-Tools time':>10}  {'Improvement':>11}")
    print("─" * 72)

    for n in stop_counts:
        matrix = random_matrix(n, seed=seed)


        t0 = time.perf_counter()
        nn_route = nearest_neighbor(matrix, start=0)
        nn_time = time.perf_counter() - t0
        nn_cost = route_cost(matrix, nn_route)


        t0 = time.perf_counter()
        ort_route = solve_tsp(matrix, start_index=0, end_index=0)
        ort_time = time.perf_counter() - t0
        ort_cost = route_cost(matrix, ort_route)

        improvement = (nn_cost - ort_cost) / nn_cost * 100 if nn_cost > 0 else 0

        print(
            f"{n:>6}  {nn_time:>10.3f}  {ort_time:>12.3f}  "
            f"{nn_cost:>10,}  {ort_cost:>13,}  {improvement:>10.1f}%"
        )

    print("\nUnits: times in seconds, costs in seconds of travel time\n")


if __name__ == "__main__":
    benchmark()
