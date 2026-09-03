from uuid import UUID

import pytest

from app.models.network_models import Location, Road
from app.repositories.network_repository import NetworkRepositoryError
from app.services.network_service import InvalidStartNodeError, NetworkAnalysisService


def location(key: str, name: str | None = None) -> Location:
    return Location(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        location_key=key,
        name=name or key,
        type="intersection",
    )


def road(start: str, end: str, *, bidirectional: bool = True) -> Road:
    return Road(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        from_location_key=start,
        to_location_key=end,
        distance_km=1.0,
        is_bidirectional=bidirectional,
    )


class FakeRepository:
    def __init__(self, locations: list[Location], roads: list[Road]) -> None:
        self.locations = locations
        self.roads = roads

    def get_locations(self) -> list[Location]:
        return self.locations

    def get_roads(self) -> list[Road]:
        return self.roads


class FailingRepository:
    def get_locations(self) -> list[Location]:
        raise NetworkRepositoryError("database unavailable")

    def get_roads(self) -> list[Road]:
        raise AssertionError("roads should not be requested after a location failure")


@pytest.fixture
def service() -> NetworkAnalysisService:
    return NetworkAnalysisService(
        FakeRepository(
            [location("A", "Alpha"), location("B", "Beta"), location("C", "Gamma")],
            [road("A", "B"), road("A", "C")],
        )
    )


def test_successful_complete_analysis(service: NetworkAnalysisService) -> None:
    result = service.analyze("A")

    assert result.start_node == "A"
    assert result.start_location_name == "Alpha"
    assert result.total_nodes == 3
    assert result.total_edges == 2
    assert result.network_density == pytest.approx(2 / 3)
    assert result.metrics_execution_time_ms >= 0
    assert result.total_execution_time_ms >= result.metrics_execution_time_ms


def test_bfs_result_is_passed_through_with_real_timing(
    service: NetworkAnalysisService,
) -> None:
    result = service.analyze("A")

    assert result.bfs.traversal_order == ["A", "B", "C"]
    assert result.bfs.visited_count == 3
    assert result.bfs.execution_time_ms >= 0


def test_dfs_result_is_passed_through_with_real_timing(
    service: NetworkAnalysisService,
) -> None:
    result = service.analyze("A")

    assert result.dfs.traversal_order == ["A", "B", "C"]
    assert result.dfs.visited_count == 3
    assert result.dfs.execution_time_ms >= 0


def test_centrality_ranking_and_most_connected_location(
    service: NetworkAnalysisService,
) -> None:
    result = service.analyze("B")

    assert [item.location_key for item in result.centrality] == ["A", "B", "C"]
    assert result.centrality[0].degree == 2
    assert result.centrality[0].centrality == 1.0
    assert result.centrality[0].rank == 1
    assert result.most_connected_location is not None
    assert result.most_connected_location.location_key == "A"
    assert result.most_connected_location.name == "Alpha"


def test_total_edges_counts_source_road_records_with_one_way_roads() -> None:
    service = NetworkAnalysisService(
        FakeRepository(
            [location("A"), location("B"), location("C")],
            [road("A", "B", bidirectional=False), road("B", "C")],
        )
    )

    assert service.analyze("A").total_edges == 2


def test_disconnected_graph_visits_only_the_start_component() -> None:
    service = NetworkAnalysisService(
        FakeRepository(
            [location("A"), location("B"), location("C"), location("D")],
            [road("A", "B"), road("C", "D")],
        )
    )

    result = service.analyze("C")

    assert result.bfs.traversal_order == ["C", "D"]
    assert result.dfs.traversal_order == ["C", "D"]
    assert result.total_nodes == 4
    assert result.network_density == pytest.approx(1 / 3)


def test_isolated_start_node_is_valid() -> None:
    service = NetworkAnalysisService(
        FakeRepository([location("A"), location("ISOLATED")], [])
    )

    result = service.analyze("ISOLATED")

    assert result.bfs.traversal_order == ["ISOLATED"]
    assert result.dfs.traversal_order == ["ISOLATED"]
    assert result.bfs.visited_count == 1
    assert result.network_density == 0.0


def test_invalid_start_node_raises_clear_error(service: NetworkAnalysisService) -> None:
    with pytest.raises(InvalidStartNodeError, match="'MISSING'.*does not exist"):
        service.analyze("MISSING")


def test_repository_failure_is_propagated() -> None:
    service = NetworkAnalysisService(FailingRepository())

    with pytest.raises(NetworkRepositoryError, match="database unavailable"):
        service.analyze("A")


def test_list_nodes_is_lightweight_and_deterministic() -> None:
    service = NetworkAnalysisService(
        FakeRepository([location("B", "Beta"), location("A", "Alpha")], [])
    )

    response = service.list_nodes()

    assert [node.location_key for node in response.nodes] == ["A", "B"]
    assert response.nodes[0].name == "Alpha"
