import pytest

from app.algorithms.metrics import (
    connection_counts,
    degree_centrality,
    most_connected_node,
    network_density,
    rank_by_degree_centrality,
)


GRAPH = {
    "A": ["C", "B", "B"],
    "B": ["D", "A"],
    "C": ["A"],
    "D": ["B"],
}


def test_connection_counts_distinct_neighbours() -> None:
    assert connection_counts(GRAPH) == {"A": 2, "B": 2, "C": 1, "D": 1}


def test_degree_centrality_is_normalized() -> None:
    assert degree_centrality(GRAPH) == pytest.approx(
        {"A": 2 / 3, "B": 2 / 3, "C": 1 / 3, "D": 1 / 3}
    )


def test_ranking_uses_degree_centrality() -> None:
    ranking = rank_by_degree_centrality(
        {"HUB": ["A", "B"], "A": ["HUB"], "B": ["HUB"]}
    )

    assert ranking == [
        {"node": "HUB", "degree": 2, "centrality": 1.0, "rank": 1},
        {"node": "A", "degree": 1, "centrality": 0.5, "rank": 2},
        {"node": "B", "degree": 1, "centrality": 0.5, "rank": 3},
    ]


def test_ranking_ties_are_ordered_by_node_id() -> None:
    ranking = rank_by_degree_centrality({"C": [], "A": [], "B": []})

    assert [item["node"] for item in ranking] == ["A", "B", "C"]
    assert [item["rank"] for item in ranking] == [1, 2, 3]


def test_most_connected_node_returns_highest_ranked_node() -> None:
    assert most_connected_node(GRAPH) == {
        "node": "A",
        "degree": 2,
        "centrality": 2 / 3,
        "rank": 1,
    }


def test_network_density_counts_each_undirected_edge_once() -> None:
    assert network_density(GRAPH) == pytest.approx(0.5)


def test_network_density_for_disconnected_graph() -> None:
    graph = {"A": ["B"], "B": ["A"], "C": [], "D": []}

    assert network_density(graph) == pytest.approx(1 / 6)


def test_empty_graph_metrics_are_safe() -> None:
    assert connection_counts({}) == {}
    assert degree_centrality({}) == {}
    assert rank_by_degree_centrality({}) == []
    assert most_connected_node({}) is None
    assert network_density({}) == 0.0


def test_single_node_graph_metrics_are_safe() -> None:
    graph = {"ONLY": []}

    assert connection_counts(graph) == {"ONLY": 0}
    assert degree_centrality(graph) == {"ONLY": 0.0}
    assert rank_by_degree_centrality(graph) == [
        {"node": "ONLY", "degree": 0, "centrality": 0.0, "rank": 1}
    ]
    assert most_connected_node(graph) == {
        "node": "ONLY",
        "degree": 0,
        "centrality": 0.0,
        "rank": 1,
    }
    assert network_density(graph) == 0.0
