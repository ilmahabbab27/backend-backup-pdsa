"""Supabase Map Seeder and Cross-Check Verification Utility for Task 5.

This module provides utilities to:
1. Load all 3 city map JSON files (Tier 1 Sparse, Tier 2 Medium, Tier 3 Dense).
2. Seed/upsert them into the Supabase `city_maps` table.
3. Query the saved maps back from Supabase.
4. Perform exhaustive cross-checks against the original JSON files to ensure 100% data integrity.
5. Generate standalone SQL migration files if direct SQL Editor execution is preferred.
"""

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import Client, create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


DEFAULT_TABLE_NAME = "task5_city_maps"

MAP_TIER_CONFIGS = [
    {
        "tier_id": "tier1_sparse",
        "tier_level": 1,
        "display_name": "Tier 1: Sparse Network (15 Bins)",
        "description": "Small-scale sparse municipal road network (37 nodes, 15 bins, 20 intersections, 42 edges).",
        "file_name": "city_map_tier1_sparse.json",
    },
    {
        "tier_id": "tier2_medium",
        "tier_level": 2,
        "display_name": "Tier 2: Medium Network (45 Bins)",
        "description": "Medium-scale urban layout (87 nodes, 45 bins, 40 intersections, 141 edges).",
        "file_name": "city_map_tier2_medium.json",
    },
    {
        "tier_id": "tier3_dense",
        "tier_level": 3,
        "display_name": "Tier 3: Dense Network (120 Bins)",
        "description": "High-density metropolitan road network (182 nodes, 120 bins, 60 intersections, 423 edges).",
        "file_name": "city_map_tier3_dense.json",
    },
]


def get_base_dir() -> Path:
    """Resolve the task5-optimization-service base directory."""
    current_file = Path(__file__).resolve()
    # Go up from app/utils/ to task5-optimization-service/
    return current_file.parent.parent.parent


def load_local_map_data(file_name: str) -> Dict[str, Any]:
    """Load and parse a local map JSON file from the data/ directory."""
    base_dir = get_base_dir()
    map_path = base_dir / "data" / file_name
    if not map_path.exists():
        raise FileNotFoundError(f"Map file not found: {map_path}")
    with open(map_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_map_record(config: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform raw map JSON into a structured record for the city_maps table."""
    nodes = raw_data.get("nodes", [])
    adj = raw_data.get("adjacency_list", {})

    bin_count = sum(1 for n in nodes if n.get("type") == "bin")
    intersection_count = sum(1 for n in nodes if n.get("type") == "intersection")
    total_waste = sum(float(n.get("weight_kg", 0)) for n in nodes if n.get("type") == "bin")
    
    # Calculate unique undirected edge count
    seen_edges = set()
    for u, neighbors in adj.items():
        for edge in neighbors:
            v = edge.get("target")
            edge_key = tuple(sorted([u, v]))
            seen_edges.add(edge_key)

    return {
        "tier_id": config["tier_id"],
        "tier_level": config["tier_level"],
        "display_name": config["display_name"],
        "description": config["description"],
        "depot_node_id": "D0",
        "dump_node_id": "T1",
        "node_count": len(nodes),
        "bin_count": bin_count,
        "intersection_count": intersection_count,
        "edge_count": len(seen_edges),
        "total_waste_kg": round(total_waste, 2),
        "nodes": nodes,
        "adjacency_list": adj,
        "metadata": {
            "version": "1.0",
            "source_file": config["file_name"],
        },
    }


def get_supabase_client(url: Optional[str] = None, key: Optional[str] = None) -> Client:
    """Initialize and return a Supabase client from params or environment variables."""
    if not SUPABASE_AVAILABLE:
        raise RuntimeError("supabase-py library is not installed.")
    supabase_url = url or os.getenv("SUPABASE_URL")
    supabase_key = key or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be provided or configured in .env"
        )
    return create_client(supabase_url, supabase_key)


def resolve_table_name(client: Client, preferred: str = DEFAULT_TABLE_NAME) -> str:
    """Detect whether preferred table or legacy city_maps exists."""
    for candidate in [preferred, "city_maps"]:
        try:
            res = client.table(candidate).select("id").limit(1).execute()
            if res is not None:
                return candidate
        except Exception:
            continue
    return preferred


def seed_all_maps_to_supabase(
    client: Optional[Client] = None,
    url: Optional[str] = None,
    key: Optional[str] = None,
    table_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Upsert all 3 map tiers into the Supabase map table (default task5_city_maps)."""
    sb_client = client or get_supabase_client(url, key)
    target_table = table_name or resolve_table_name(sb_client, DEFAULT_TABLE_NAME)
    results = []

    for cfg in MAP_TIER_CONFIGS:
        raw_data = load_local_map_data(cfg["file_name"])
        record = build_map_record(cfg, raw_data)
        
        response = (
            sb_client.table(target_table)
            .upsert(record, on_conflict="tier_id")
            .execute()
        )
        results.append({
            "tier_id": cfg["tier_id"],
            "status": "success",
            "table": target_table,
            "nodes_count": record["node_count"],
            "edges_count": record["edge_count"],
            "data": response.data,
        })
    return results


def cross_check_maps_with_supabase(
    client: Optional[Client] = None,
    url: Optional[str] = None,
    key: Optional[str] = None,
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch all 3 maps from Supabase and cross-check against local JSON files."""
    sb_client = client or get_supabase_client(url, key)
    target_table = table_name or resolve_table_name(sb_client, DEFAULT_TABLE_NAME)
    verification_report = {
        "all_passed": True,
        "table_name": target_table,
        "tiers": {},
    }

    for cfg in MAP_TIER_CONFIGS:
        tier_id = cfg["tier_id"]
        local_data = load_local_map_data(cfg["file_name"])
        expected_record = build_map_record(cfg, local_data)

        # Query from Supabase
        response = (
            sb_client.table(target_table)
            .select("*")
            .eq("tier_id", tier_id)
            .single()
            .execute()
        )

        remote_data = response.data
        if not remote_data:
            verification_report["all_passed"] = False
            verification_report["tiers"][tier_id] = {
                "passed": False,
                "error": f"Record with tier_id '{tier_id}' not found in Supabase table '{target_table}'.",
            }
            continue

        # Check nodes
        local_nodes = {n["id"]: n for n in expected_record["nodes"]}
        remote_nodes = {n["id"]: n for n in remote_data.get("nodes", [])}

        node_mismatches = []
        if len(local_nodes) != len(remote_nodes):
            node_mismatches.append(
                f"Node count mismatch: expected {len(local_nodes)}, got {len(remote_nodes)}"
            )

        for node_id, local_n in local_nodes.items():
            if node_id not in remote_nodes:
                node_mismatches.append(f"Missing node: {node_id}")
                continue
            rem_n = remote_nodes[node_id]
            if local_n.get("type") != rem_n.get("type"):
                node_mismatches.append(f"Node {node_id} type mismatch: {local_n.get('type')} != {rem_n.get('type')}")
            if not math.isclose(float(local_n.get("lat", 0)), float(rem_n.get("lat", 0)), abs_tol=1e-5):
                node_mismatches.append(f"Node {node_id} lat mismatch: {local_n.get('lat')} != {rem_n.get('lat')}")
            if not math.isclose(float(local_n.get("lon", 0)), float(rem_n.get("lon", 0)), abs_tol=1e-5):
                node_mismatches.append(f"Node {node_id} lon mismatch: {local_n.get('lon')} != {rem_n.get('lon')}")
            if not math.isclose(float(local_n.get("weight_kg", 0)), float(rem_n.get("weight_kg", 0)), abs_tol=1e-2):
                node_mismatches.append(f"Node {node_id} weight mismatch: {local_n.get('weight_kg')} != {rem_n.get('weight_kg')}")

        # Check adjacency list
        local_adj = expected_record["adjacency_list"]
        remote_adj = remote_data.get("adjacency_list", {})
        adj_mismatches = []

        if set(local_adj.keys()) != set(remote_adj.keys()):
            adj_mismatches.append("Adjacency list node keys mismatch")

        for u, l_neighbors in local_adj.items():
            r_neighbors = remote_adj.get(u, [])
            l_dict = {nbr["target"]: float(nbr["distance_km"]) for nbr in l_neighbors}
            r_dict = {nbr["target"]: float(nbr["distance_km"]) for nbr in r_neighbors}
            if set(l_dict.keys()) != set(r_dict.keys()):
                adj_mismatches.append(f"Node {u} neighbor targets mismatch")
                continue
            for target, dist in l_dict.items():
                if not math.isclose(dist, r_dict.get(target, -1), abs_tol=1e-3):
                    adj_mismatches.append(f"Edge {u}->{target} distance mismatch: {dist} != {r_dict.get(target)}")

        # Summary check
        tier_passed = (
            len(node_mismatches) == 0
            and len(adj_mismatches) == 0
            and int(remote_data.get("node_count", 0)) == expected_record["node_count"]
            and int(remote_data.get("bin_count", 0)) == expected_record["bin_count"]
            and int(remote_data.get("edge_count", 0)) == expected_record["edge_count"]
        )

        if not tier_passed:
            verification_report["all_passed"] = False

        verification_report["tiers"][tier_id] = {
            "passed": tier_passed,
            "node_count": len(remote_nodes),
            "edge_count": remote_data.get("edge_count"),
            "bin_count": remote_data.get("bin_count"),
            "node_mismatches": node_mismatches,
            "adj_mismatches": adj_mismatches,
        }

    return verification_report


def generate_sql_insert_statements(table_name: str = DEFAULT_TABLE_NAME) -> str:
    """Generate a complete SQL file containing CREATE TABLE and INSERT for all 3 maps."""
    sql_lines = [
        "-- ========================================================",
        f"-- SMART CITY IDSS: {table_name.upper()} SCHEMA & SEED DATA",
        "-- Supports Tier 1 (Sparse), Tier 2 (Medium), Tier 3 (Dense)",
        "-- ========================================================\n",
        f"CREATE TABLE IF NOT EXISTS public.{table_name} (",
        "    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),",
        "    tier_id TEXT UNIQUE NOT NULL,",
        "    tier_level INTEGER NOT NULL CHECK (tier_level IN (1, 2, 3)),",
        "    display_name TEXT NOT NULL,",
        "    description TEXT,",
        "    depot_node_id TEXT NOT NULL DEFAULT 'D0',",
        "    dump_node_id TEXT NOT NULL DEFAULT 'T1',",
        "    node_count INTEGER NOT NULL DEFAULT 0,",
        "    bin_count INTEGER NOT NULL DEFAULT 0,",
        "    intersection_count INTEGER NOT NULL DEFAULT 0,",
        "    edge_count INTEGER NOT NULL DEFAULT 0,",
        "    total_waste_kg NUMERIC(10,2) NOT NULL DEFAULT 0,",
        "    nodes JSONB NOT NULL DEFAULT '[]'::jsonb,",
        "    adjacency_list JSONB NOT NULL DEFAULT '{}'::jsonb,",
        "    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),",
        "    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");\n",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_tier_id ON public.{table_name} (tier_id);\n",
        f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY;\n",
        f"CREATE POLICY IF NOT EXISTS \"Allow all access to {table_name}\"",
        f"ON public.{table_name} FOR ALL TO anon, authenticated, service_role USING (true) WITH CHECK (true);\n",
    ]

    for cfg in MAP_TIER_CONFIGS:
        raw_data = load_local_map_data(cfg["file_name"])
        rec = build_map_record(cfg, raw_data)

        nodes_json_str = json.dumps(rec["nodes"]).replace("'", "''")
        adj_json_str = json.dumps(rec["adjacency_list"]).replace("'", "''")
        meta_json_str = json.dumps(rec["metadata"]).replace("'", "''")
        desc_escaped = rec["description"].replace("'", "''")
        name_escaped = rec["display_name"].replace("'", "''")

        sql_lines.append(
            f"INSERT INTO public.{table_name} (\n"
            f"    tier_id, tier_level, display_name, description,\n"
            f"    depot_node_id, dump_node_id, node_count, bin_count,\n"
            f"    intersection_count, edge_count, total_waste_kg,\n"
            f"    nodes, adjacency_list, metadata\n"
            f") VALUES (\n"
            f"    '{rec['tier_id']}', {rec['tier_level']}, '{name_escaped}', '{desc_escaped}',\n"
            f"    '{rec['depot_node_id']}', '{rec['dump_node_id']}', {rec['node_count']}, {rec['bin_count']},\n"
            f"    {rec['intersection_count']}, {rec['edge_count']}, {rec['total_waste_kg']},\n"
            f"    '{nodes_json_str}'::jsonb,\n"
            f"    '{adj_json_str}'::jsonb,\n"
            f"    '{meta_json_str}'::jsonb\n"
            f")\n"
            f"ON CONFLICT (tier_id) DO UPDATE SET\n"
            f"    tier_level = EXCLUDED.tier_level,\n"
            f"    display_name = EXCLUDED.display_name,\n"
            f"    description = EXCLUDED.description,\n"
            f"    depot_node_id = EXCLUDED.depot_node_id,\n"
            f"    dump_node_id = EXCLUDED.dump_node_id,\n"
            f"    node_count = EXCLUDED.node_count,\n"
            f"    bin_count = EXCLUDED.bin_count,\n"
            f"    intersection_count = EXCLUDED.intersection_count,\n"
            f"    edge_count = EXCLUDED.edge_count,\n"
            f"    total_waste_kg = EXCLUDED.total_waste_kg,\n"
            f"    nodes = EXCLUDED.nodes,\n"
            f"    adjacency_list = EXCLUDED.adjacency_list,\n"
            f"    metadata = EXCLUDED.metadata,\n"
            f"    updated_at = now();\n"
        )

    return "\n".join(sql_lines)


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("SMART CITY MAP SEEDER & VERIFIER")
    print("=" * 60)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("\n[!] SUPABASE_URL or SUPABASE_KEY is not set.")
        print("Generating standalone SQL migration script 'seed_city_maps.sql'...")
        base_dir = get_base_dir()
        sql_path = base_dir / "data" / "seed_city_maps.sql"
        sql_content = generate_sql_insert_statements(DEFAULT_TABLE_NAME)
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)
        print(f"[OK] Created SQL file at: {sql_path}")
        print(f"    Size: {len(sql_content):,} bytes")
        print("\nYou can run this SQL script directly in the Supabase SQL Editor.")
        sys.exit(0)

    print(f"Connecting to Supabase at: {url}")
    try:
        client = get_supabase_client(url, key)
        active_table = resolve_table_name(client, DEFAULT_TABLE_NAME)
        print(f"Target table resolved: '{active_table}'")
        print(f"Seeding all 3 maps into '{active_table}' table...")
        results = seed_all_maps_to_supabase(client, table_name=active_table)
        for r in results:
            print(f"  [OK] Seeded {r['tier_id']}: {r['nodes_count']} nodes, {r['edges_count']} edges")

        print("\nStarting exhaustive cross-check verification against local JSON files...")
        report = cross_check_maps_with_supabase(client, table_name=active_table)
        print(f"All passed: {report['all_passed']} (Checked from '{report['table_name']}')")
        for tid, tinfo in report["tiers"].items():
            status = "PASS" if tinfo["passed"] else "FAIL"
            print(f"  - [{status}] {tid}: {tinfo['node_count']} nodes, {tinfo['bin_count']} bins, {tinfo['edge_count']} edges")
            if not tinfo["passed"]:
                print(f"      Errors: {tinfo.get('node_mismatches', []) + tinfo.get('adj_mismatches', [])}")
    except Exception as e:
        print(f"[!] Error: {e}")
        sys.exit(1)
