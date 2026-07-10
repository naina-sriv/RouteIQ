import logging
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from config import SOLVER_TIME_LIMIT_SECONDS

logger = logging.getLogger(__name__)


def solve_tsp(
    matrix: list[list[int]],
    start_index: int = 0,
    end_index: int = 0,
) -> list[int]:
    n = len(matrix)
    if n < 2:
        raise ValueError("Need at least 2 stops")
    if n > 20:
        raise ValueError("Maximum 20 stops supported")

    manager = pywrapcp.RoutingIndexManager(n, 1, [start_index], [end_index])
    routing = pywrapcp.RoutingModel(manager)


    int_matrix = [[int(matrix[i][j]) for j in range(n)] for i in range(n)]
    transit_cb = routing.RegisterTransitMatrix(int_matrix)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = SOLVER_TIME_LIMIT_SECONDS

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        logger.warning("OR-Tools found no solution, using nearest-neighbor fallback")
        return _nearest_neighbor(matrix, start_index, end_index)

    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route


def _nearest_neighbor(matrix: list[list[int]], start: int, end: int) -> list[int]:
    n = len(matrix)
    unvisited = set(range(n)) - {start, end}
    route = [start]
    current = start
    while unvisited:
        nearest = min(unvisited, key=lambda j: matrix[current][j])
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    route.append(end)
    return route