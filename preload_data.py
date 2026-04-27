from pathlib import Path

import osmnx as ox

from station_store import fetch_station_nodes_for_place, save_station_nodes

import pickle

PLACE_NAME = "Munich, Bavaria, Germany"
GRAPH_CACHE_FILE = "cache/munich_rail.graphml"
STATION_CACHE_FILE = "cache/munich_station_nodes_citywide.json"


def main():
    cache_dir = Path("cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Munich rail graph...")
    graph = ox.graph_from_place(
        PLACE_NAME,
        custom_filter='["railway"~"rail|subway|tram"]',
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(graph, GRAPH_CACHE_FILE)
    print(f"Saved graph cache: {GRAPH_CACHE_FILE}")
    with open("cache/munich_rail.pkl", "wb") as f:
        pickle.dump(graph, f)
    print("Loading Munich train stations...")
    station_nodes = fetch_station_nodes_for_place(graph, PLACE_NAME)
    save_station_nodes(station_nodes, STATION_CACHE_FILE)
    print(f"Saved station cache: {STATION_CACHE_FILE} ({len(station_nodes)} stations)")


if __name__ == "__main__":
    main()
