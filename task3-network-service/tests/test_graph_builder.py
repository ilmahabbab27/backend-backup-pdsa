from uuid import UUID

import pytest

from app.algorithms.graph_builder import build_adjacency
from app.models.network_models import Location, Road


def location(key: str) -> Location:
    return Location(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        location_key=key,
        name=key.title(),
        type="intersection",
    )


def road(
    start: str,
    end: str,
    *,
    bidirectional: bool = True,
) -> Road:
    return Road(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        from_location_key=start,
        to_location_key=end,
        distance_km=1.0,
        is_bidirectional=bidirectional,
    )


def test_builds_normal_graph_with_sorted_neighbours() -> None:
    graph = build_adjacency(
        [location("C"), location("A"), location("B")],
        [road("A", "C"), road("A", "B")],
    )

    assert graph == {"A": ["B", "C"], "B": ["A"], "C": ["A"]}


def test_bidirectional_road_adds_both_directions() -> None:
    graph = build_adjacency([location("A"), location("B")], [road("A", "B")])

    assert graph == {"A": ["B"], "B": ["A"]}


def test_one_way_road_adds_only_forward_direction() -> None:
    graph = build_adjacency(
        [location("A"), location("B")],
        [road("A", "B", bidirectional=False)],
    )

    assert graph == {"A": ["B"], "B": []}


def test_isolated_location_is_preserved() -> None:
    graph = build_adjacency([location("A"), location("ISOLATED")], [])

    assert graph == {"A": [], "ISOLATED": []}


def test_duplicate_roads_do_not_duplicate_neighbours() -> None:
    graph = build_adjacency(
        [location("A"), location("B")],
        [road("A", "B"), road("A", "B")],
    )

    assert graph == {"A": ["B"], "B": ["A"]}


def test_disconnected_components_are_preserved() -> None:
    graph = build_adjacency(
        [location("A"), location("B"), location("C"), location("D")],
        [road("A", "B"), road("C", "D")],
    )

    assert graph == {"A": ["B"], "B": ["A"], "C": ["D"], "D": ["C"]}


def test_unknown_road_endpoint_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unknown to-location 'MISSING'"):
        build_adjacency([location("A")], [road("A", "MISSING")])
