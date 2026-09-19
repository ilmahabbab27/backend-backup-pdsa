"""Unit tests for the Task 4 ranking algorithms.

These test the algorithm layer directly with in-memory candidates, so they
need no database and run fast. Data mirrors the seeded hospitals:

  central-hospital   : capacity 300, load 180 -> availability 120
  community-hospital : capacity 180, load  95 -> availability  85

Distances below are illustrative haversine-style values from the
'residential' location.
"""
from app.algorithms import ranking
from app.algorithms.heuristic_scoring import heuristic_scoring
from app.algorithms.linear_search import linear_search
from app.algorithms.weighted_ranking import weighted_ranking


def _candidates() -> list[dict]:
    """Two hospital candidates resembling the seeded data."""
    return [
        {
            "location_key": "central-hospital",
            "name": "Central Hospital",
            "facility_type": "hospital",
            "distance_km": 0.80,
            "capacity": 300,
            "current_load": 180,
            "availability": 120,
        },
        {
            "location_key": "community-hospital",
            "name": "Community Hospital",
            "facility_type": "hospital",
            "distance_km": 0.30,
            "capacity": 180,
            "current_load": 95,
            "availability": 85,
        },
    ]


def _best(candidates: list[dict]) -> dict:
    """Return the highest-scoring candidate (ties -> shorter distance)."""
    return sorted(candidates, key=lambda c: (-c["score"], c["distance_km"]))[0]


def test_linear_search_picks_nearest():
    """Baseline should pick the closest facility regardless of capacity."""
    result = ranking.linear_search(_candidates())
    assert _best(result)["location_key"] == "community-hospital"


def test_weighted_ranking_distance_heavy_prefers_nearest():
    """When distance dominates, the nearer hospital should win."""
    weights = {"distance": 0.8, "capacity": 0.1, "availability": 0.1}
    result = ranking.weighted_ranking(_candidates(), weights)
    assert _best(result)["location_key"] == "community-hospital"


def test_weighted_ranking_capacity_heavy_prefers_bigger():
    """When capacity dominates, the larger hospital should win."""
    weights = {"distance": 0.1, "capacity": 0.8, "availability": 0.1}
    result = ranking.weighted_ranking(_candidates(), weights)
    assert _best(result)["location_key"] == "central-hospital"


def test_weighted_ranking_all_scores_between_zero_and_one():
    """Normalised weighted scores must stay within [0, 1]."""
    weights = {"distance": 0.5, "capacity": 0.3, "availability": 0.2}
    result = ranking.weighted_ranking(_candidates(), weights)
    for c in result:
        assert 0.0 <= c["score"] <= 1.0


def test_weighted_ranking_zero_weights_defaults_to_equal():
    """All-zero weights must not crash; criteria are treated equally."""
    weights = {"distance": 0.0, "capacity": 0.0, "availability": 0.0}
    result = ranking.weighted_ranking(_candidates(), weights)
    assert all("score" in c for c in result)


def test_heuristic_penalises_full_facility():
    """A full facility (availability <= 0) should score below a free one."""
    candidates = _candidates()
    candidates[0]["availability"] = 0  # make central-hospital full
    candidates[0]["current_load"] = 300
    result = ranking.heuristic_scoring(candidates)
    scores = {c["location_key"]: c["score"] for c in result}
    assert scores["community-hospital"] > scores["central-hospital"]


def test_normalise_handles_equal_values():
    """When all values are equal, every item normalises to 1.0."""
    out = ranking._normalise_min_max([5.0, 5.0, 5.0], higher_is_better=True)
    assert out == [1.0, 1.0, 1.0]


def test_task4_algorithm_modules_are_available_as_separate_files():
    """The API should expose each ranking algorithm as its own module."""
    assert callable(linear_search)
    assert callable(weighted_ranking)
    assert callable(heuristic_scoring)
