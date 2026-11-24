"""
Diagnostic utility to inspect OR-Tools index manager node mappings.
Run directly: python utils/debug.py
"""

from ortools.constraint_solver import pywrapcp


def debug_node_mapping(num_stops: int = 5) -> None:
    manager = pywrapcp.RoutingIndexManager(num_stops, 1, [0], [0])
    routing = pywrapcp.RoutingModel(manager)

    print(f"num_stops={num_stops}, routing.Size()={routing.Size()}, routing.nodes()={routing.nodes()}")

    for idx in range(routing.Size() + 5):
        try:
            node = manager.IndexToNode(idx)
            print(f"  idx={idx} -> node={node}")
        except Exception as err:
            print(f"  idx={idx} -> ERROR: {err}")


if __name__ == "__main__":
    debug_node_mapping()
