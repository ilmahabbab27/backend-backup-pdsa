"""Tests for Supabase map data integrity and seeding utilities."""

import json
from pathlib import Path
import pytest

from app.utils.supabase_map_seeder import (
    MAP_TIER_CONFIGS,
    build_map_record,
    generate_sql_insert_statements,
    get_base_dir,
    load_local_map_data,
)


def test_load_all_local_maps():
    """Verify that all 3 tier map files exist and are valid JSON."""
    for cfg in MAP_TIER_CONFIGS:
        data = load_local_map_data(cfg["file_name"])
        assert "nodes" in data
        assert "adjacency_list" in data
        assert len(data["nodes"]) > 0
        assert len(data["adjacency_list"]) > 0


def test_map_record_builder_integrity():
    """Verify that records built for city_maps have accurate counts and anchor nodes."""
    expected_counts = {
        "tier1_sparse": {"bins": 15, "nodes": 37, "edges": 42},
        "tier2_medium": {"bins": 45, "nodes": 87, "edges": 141},
        "tier3_dense": {"bins": 120, "nodes": 182, "edges": 423},
    }

    for cfg in MAP_TIER_CONFIGS:
        raw_data = load_local_map_data(cfg["file_name"])
        record = build_map_record(cfg, raw_data)

        tier_id = cfg["tier_id"]
        assert record["tier_id"] == tier_id
        assert record["tier_level"] == cfg["tier_level"]
        assert record["depot_node_id"] == "D0"
        assert record["dump_node_id"] == "T1"
        assert record["bin_count"] == expected_counts[tier_id]["bins"]
        assert record["node_count"] == expected_counts[tier_id]["nodes"]
        assert record["edge_count"] == expected_counts[tier_id]["edges"]
        assert record["total_waste_kg"] > 0

        # Verify all node IDs are unique
        node_ids = [n["id"] for n in record["nodes"]]
        assert len(node_ids) == len(set(node_ids))

        # Verify D0 and T1 exist in nodes
        assert "D0" in node_ids
        assert "T1" in node_ids


def test_sql_generation_integrity():
    """Verify that generated SQL contains DDL and inserts for all 3 map tiers."""
    sql = generate_sql_insert_statements("task5_city_maps")
    assert "CREATE TABLE IF NOT EXISTS public.task5_city_maps" in sql
    assert "tier1_sparse" in sql
    assert "tier2_medium" in sql
    assert "tier3_dense" in sql
    assert "ON CONFLICT (tier_id) DO UPDATE" in sql

