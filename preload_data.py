from pathlib import Path

import osmnx as ox

from station_store import (
    fetch_station_mappings_for_place,
    fetch_station_nodes_for_place,
    save_station_mappings,
    save_station_nodes,
)


PLACE_NAME = "Munich, Bavaria, Germany"
GRAPH_CACHE_FILE = "cache/munich_drive.graphml"
RAIL_GRAPH_CACHE_FILE = "cache/munich_ubahn_rail.graphml"
STATION_CACHE_FILE = "cache/munich_station_nodes_citywide.json"
STATION_MAPPING_CACHE_FILE = "cache/munich_station_mappings_citywide.json"


def main():
    cache_dir = Path("cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Munich drive graph...")
    graph = ox.graph_from_place(
        PLACE_NAME,
        network_type="drive",
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(graph, GRAPH_CACHE_FILE)
    print(f"Saved graph cache: {GRAPH_CACHE_FILE}")

    print("Loading Munich U-Bahn rail graph...")
    rail_graph = ox.graph_from_place(
        PLACE_NAME,
        custom_filter='["railway"~"subway|light_rail"]',
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(rail_graph, RAIL_GRAPH_CACHE_FILE)
    print(f"Saved rail graph cache: {RAIL_GRAPH_CACHE_FILE}")

    print("Loading Munich train stations...")
    station_nodes = fetch_station_nodes_for_place(graph, PLACE_NAME)
    save_station_nodes(station_nodes, STATION_CACHE_FILE)
    print(f"Saved station cache: {STATION_CACHE_FILE} ({len(station_nodes)} stations)")

    print("Building station mappings between road and U-Bahn graphs...")
    station_mappings = fetch_station_mappings_for_place(graph, rail_graph, PLACE_NAME)
    save_station_mappings(station_mappings, STATION_MAPPING_CACHE_FILE)
    print(f"Saved station mapping cache: {STATION_MAPPING_CACHE_FILE} ({len(station_mappings)} mappings)")


if __name__ == "__main__":
    main()
