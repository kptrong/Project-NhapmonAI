import json
from pathlib import Path
from typing import Dict, List

import osmnx as ox


StationRecord = Dict[str, float | int | str]


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


def fetch_station_records_for_place(drive_graph, rail_graph, place_name: str) -> List[StationRecord]:
    tags = {"railway": ["station", "halt", "stop"]}
    features = ox.features_from_place(place_name, tags=tags)

    station_records = []
    seen = set()
    for _, row in features.iterrows():
        station_type = str(row.get("station") or "").strip().lower()
        subway_flag = str(row.get("subway") or "").strip().lower()
        if station_type != "subway" and subway_flag not in {"yes", "1", "true"}:
            continue

        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)
        drive_node = int(ox.nearest_nodes(drive_graph, lon, lat))
        rail_node = int(ox.nearest_nodes(rail_graph, lon, lat))
        key = (drive_node, rail_node)
        if key in seen:
            continue
        seen.add(key)

        station_records.append(
            {
                "name": str(row.get("name") or row.get("ref") or "Station"),
                "lat": float(lat),
                "lon": float(lon),
                "drive_node": drive_node,
                "rail_node": rail_node,
            }
        )

    return station_records


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


def save_station_records(station_records: List[StationRecord], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"station_records": station_records}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_station_records(file_path: str) -> List[StationRecord]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []

    raw_records = payload.get("station_records")
    if not isinstance(raw_records, list):
        # Old cache format only contains drive nodes, so force rebuild.
        return []

    records = []
    for row in raw_records:
        if not isinstance(row, dict):
            continue
        try:
            records.append(
                {
                    "name": str(row.get("name") or "Station"),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "drive_node": int(row["drive_node"]),
                    "rail_node": int(row["rail_node"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    return records
