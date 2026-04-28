from pathlib import Path

import osmnx as ox

from station_store import fetch_station_records_for_place, save_station_records


PLACE_NAME = "Munich, Bavaria, Germany"
DRIVE_GRAPH_CACHE_FILE = "cache/munich_drive.graphml"
RAIL_GRAPH_CACHE_FILE = "cache/munich_rail.graphml"
STATION_CACHE_FILE = "cache/munich_station_nodes_citywide.json"


def main():
    cache_dir = Path("cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Munich drive graph...")
    drive_graph = ox.graph_from_place(
        PLACE_NAME,
        network_type="drive",
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(drive_graph, DRIVE_GRAPH_CACHE_FILE)
    print(f"Saved drive graph cache: {DRIVE_GRAPH_CACHE_FILE}")

    print("Loading Munich rail graph...")
    rail_graph = ox.graph_from_place(
        PLACE_NAME,
        network_type="all",
        custom_filter='["railway"="subway"]',
        simplify=True,
        retain_all=True,
    )
    ox.save_graphml(rail_graph, RAIL_GRAPH_CACHE_FILE)
    print(f"Saved rail graph cache: {RAIL_GRAPH_CACHE_FILE}")

    print("Loading Munich train stations...")
    station_records = fetch_station_records_for_place(drive_graph, rail_graph, PLACE_NAME)
    save_station_records(station_records, STATION_CACHE_FILE)
    print(f"Saved station cache: {STATION_CACHE_FILE} ({len(station_records)} stations)")


if __name__ == "__main__":
    main()
