import json
from pathlib import Path
from typing import List

import osmnx as ox


def _extract_point_coords(geometry):
    if geometry.geom_type == "Point":
        return geometry.y, geometry.x

    point = geometry.centroid
    return point.y, point.x


def fetch_station_nodes(graph, center_lat: float, center_lon: float, dist: int) -> List[int]:
    tags = {"railway": ["station", "halt", "stop"]}
    features = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist)

    station_node_set = set()
    for _, row in features.iterrows():
        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)
        station_node = ox.nearest_nodes(graph, lon, lat)
        station_node_set.add(int(station_node))

    return sorted(station_node_set)


def fetch_station_nodes_for_place(graph, place_name: str) -> List[int]:
    tags = {"railway": ["station", "halt", "stop"]}
    features = ox.features_from_place(place_name, tags=tags)

    station_node_set = set()
    for _, row in features.iterrows():
        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)
        station_node = ox.nearest_nodes(graph, lon, lat)
        station_node_set.add(int(station_node))

    return sorted(station_node_set)


def save_station_nodes(station_nodes: List[int], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"station_nodes": station_nodes}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_station_nodes(file_path: str) -> List[int]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        nodes = payload.get("station_nodes", [])
        return [int(node) for node in nodes]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
