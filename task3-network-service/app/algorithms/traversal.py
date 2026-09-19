"""Pure breadth-first and depth-first graph traversal algorithms."""

from collections import deque
from collections.abc import Hashable, Iterable, Mapping
from typing import TypeVar


# T3DS: Generic graph node and traversal result structure used by the network analysis algorithms.
Node = TypeVar("Node", bound=Hashable)
Adjacency = Mapping[Node, Iterable[Node]]
TraversalResult = tuple[list[Node], int]


# T3DS: Return neighbouring nodes in stable order so traversal output stays deterministic.
def _ordered_neighbours(graph: Adjacency[Node], node: Node) -> list[Node]:
    """Return neighbours in stable order without changing the input graph."""
    return sorted(graph[node], key=str)


# T3DS: Validate the starting node before traversal begins so invalid network requests are detected early.
def _validate_start(graph: Adjacency[Node], start: Node) -> None:
    """Raise a clear error when a traversal cannot begin at ``start``."""
    if start not in graph:
        raise ValueError(f"Start node {start!r} does not exist in the graph")


# T3DS: Explore the connected component from the start node using a FIFO queue, layer by layer.
def breadth_first_search(graph: Adjacency[Node], start: Node) -> TraversalResult[Node]:
    """Traverse the component containing ``start`` in breadth-first order.

    Time complexity is O(V + E) and auxiliary space complexity is O(V).
    """
    _validate_start(graph, start)

    visited = {start}
    queue = deque([start])
    traversal_order: list[Node] = []

    while queue:
        node = queue.popleft()
        traversal_order.append(node)

        for neighbour in _ordered_neighbours(graph, node):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)

    return traversal_order, len(visited)


# T3DS: Explore the connected component from the start node using an explicit stack, following deep branches first.
def depth_first_search(graph: Adjacency[Node], start: Node) -> TraversalResult[Node]:
    """Traverse the component containing ``start`` using an explicit stack.

    Time complexity is O(V + E) and auxiliary space complexity is O(V).
    """
    _validate_start(graph, start)

    visited: set[Node] = set()
    stack = [start]
    traversal_order: list[Node] = []

    while stack:
        node = stack.pop()
        if node in visited:
            continue

        visited.add(node)
        traversal_order.append(node)

        # Reverse the sorted order because a stack processes its last item first.
        for neighbour in reversed(_ordered_neighbours(graph, node)):
            if neighbour not in visited:
                stack.append(neighbour)

    return traversal_order, len(visited)
