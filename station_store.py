import json
import math
from pathlib import Path
from typing import List

import osmnx as ox


def _extract_point_coords(geometry):
    if geometry.geom_type == "Point":
        return geometry.y, geometry.x

    point = geometry.centroid
    return point.y, point.x


def _distance_sq(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    dlat = lat_a - lat_b
    dlon = lon_a - lon_b
    return dlat * dlat + dlon * dlon


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371000 * c


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


def fetch_station_mappings_for_place(road_graph, rail_graph, place_name: str) -> List[dict]:
    """
    Build station mappings between road and U-Bahn rail graphs.
    Each entry has: name, lat, lon, road_node, rail_node.
    """
    tags = {
        "railway": ["station", "halt", "stop"],
        "station": ["subway"],
        "subway": ["yes"],
    }
    features = ox.features_from_place(place_name, tags=tags)

    station_mappings = []
    dedup = set()
    max_road_transfer_m = 250.0
    max_rail_transfer_m = 250.0

    for _, row in features.iterrows():
        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)

        try:
            road_node = int(ox.nearest_nodes(road_graph, lon, lat))
            rail_node = int(ox.nearest_nodes(rail_graph, lon, lat))
        except Exception:
            continue

        road_lat = float(road_graph.nodes[road_node]["y"])
        road_lon = float(road_graph.nodes[road_node]["x"])
        rail_lat = float(rail_graph.nodes[rail_node]["y"])
        rail_lon = float(rail_graph.nodes[rail_node]["x"])

        road_transfer_m = _haversine_m(lat, lon, road_lat, road_lon)
        rail_transfer_m = _haversine_m(lat, lon, rail_lat, rail_lon)
        transfer_total_m = road_transfer_m + rail_transfer_m

        # Keep only stations with reasonable transfer continuity.
        if road_transfer_m > max_road_transfer_m or rail_transfer_m > max_rail_transfer_m:
            continue

        key = (road_node, rail_node)
        if key in dedup:
            continue
        dedup.add(key)

        station_mappings.append(
            {
                "name": str(row.get("name", "Station")),
                "lat": float(lat),
                "lon": float(lon),
                "road_node": road_node,
                "rail_node": rail_node,
                "road_transfer_m": road_transfer_m,
                "rail_transfer_m": rail_transfer_m,
                "transfer_total_m": transfer_total_m,
            }
        )

    return station_mappings


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


def save_station_mappings(station_mappings: List[dict], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"station_mappings": station_mappings}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_station_mappings(file_path: str) -> List[dict]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mappings = payload.get("station_mappings", [])
        result = []
        for item in mappings:
            result.append(
                {
                    "name": str(item.get("name", "Station")),
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "road_node": int(item["road_node"]),
                    "rail_node": int(item["rail_node"]),
                    "road_transfer_m": float(item.get("road_transfer_m", -1.0)),
                    "rail_transfer_m": float(item.get("rail_transfer_m", -1.0)),
                    "transfer_total_m": float(item.get("transfer_total_m", -1.0)),
                }
            )
        return result
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        return []
