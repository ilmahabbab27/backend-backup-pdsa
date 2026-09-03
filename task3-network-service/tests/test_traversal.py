import pytest

from app.algorithms.traversal import breadth_first_search, depth_first_search


CONNECTED_GRAPH = {
    "A": ["C", "B"],
    "B": ["D", "A"],
    "C": ["D", "A"],
    "D": ["C", "B"],
}

CYCLIC_GRAPH = {
    "A": ["B", "C"],
    "B": ["C", "A"],
    "C": ["A", "B"],
}

DISCONNECTED_GRAPH = {
    "A": ["B"],
    "B": ["A"],
    "C": ["D"],
    "D": ["C"],
}


def test_bfs_connected_graph_is_deterministic() -> None:
    order, visited_count = breadth_first_search(CONNECTED_GRAPH, "A")

    assert order == ["A", "B", "C", "D"]
    assert visited_count == 4


def test_bfs_cyclic_graph_does_not_revisit_nodes() -> None:
    order, visited_count = breadth_first_search(CYCLIC_GRAPH, "A")

    assert order == ["A", "B", "C"]
    assert visited_count == 3


def test_bfs_disconnected_graph_visits_only_start_component() -> None:
    order, visited_count = breadth_first_search(DISCONNECTED_GRAPH, "C")

    assert order == ["C", "D"]
    assert visited_count == 2


def test_bfs_invalid_start_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Start node 'Z' does not exist"):
        breadth_first_search(CONNECTED_GRAPH, "Z")


def test_dfs_connected_graph_is_deterministic() -> None:
    order, visited_count = depth_first_search(CONNECTED_GRAPH, "A")

    assert order == ["A", "B", "D", "C"]
    assert visited_count == 4


def test_dfs_cyclic_graph_does_not_revisit_nodes() -> None:
    order, visited_count = depth_first_search(CYCLIC_GRAPH, "A")

    assert order == ["A", "B", "C"]
    assert visited_count == 3


def test_dfs_disconnected_graph_visits_only_start_component() -> None:
    order, visited_count = depth_first_search(DISCONNECTED_GRAPH, "C")

    assert order == ["C", "D"]
    assert visited_count == 2


def test_dfs_invalid_start_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Start node 'Z' does not exist"):
        depth_first_search(CONNECTED_GRAPH, "Z")
