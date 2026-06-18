from ortools.constraint_solver import routing_enums_pb2, pywrapcp

n = 5
manager = pywrapcp.RoutingIndexManager(n, 1, [0], [0])
routing = pywrapcp.RoutingModel(manager)

print(f"n={n}, routing.Size()={routing.Size()}, routing.Nodes()={routing.nodes()}")

for idx in range(routing.Size() + 5):
    try:
        node = manager.IndexToNode(idx)
        print(f"  idx={idx} -> node={node}")
    except Exception as e:
        print(f"  idx={idx} -> ERROR: {e}")