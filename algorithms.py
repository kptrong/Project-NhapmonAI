import heapq
import math
from typing import Dict, List, Tuple


def _edge_length(edge_data: dict) -> float:
    """Return edge length for both Graph and MultiDiGraph adjacency formats."""
    if "length" in edge_data:
        return float(edge_data.get("length", 1.0))

    min_length = float("inf")
    for attrs in edge_data.values():
        length = float(attrs.get("length", 1.0))
        if length < min_length:
            min_length = length

    return min_length if min_length != float("inf") else 1.0


def _neighbors_with_cost(graph, node: int) -> List[Tuple[int, float]]:
    neighbors = []
    for neighbor, edge_data in graph[node].items():
        neighbors.append((neighbor, _edge_length(edge_data)))
    return neighbors


def _reconstruct_path(came_from: Dict[int, int], start: int, end: int) -> List[int]:
    if start == end:
        return [start]
    if end not in came_from:
        return []

    path = [end]
    current = end
    while current != start:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def dijkstra_search(graph, start: int, end: int) -> Tuple[List[int], float, int]:
    """Return (path, total_distance_m, expanded_nodes)."""
    distances = {start: 0.0}
    came_from: Dict[int, int] = {}
    visited = set()
    expanded_nodes = 0

    pq = [(0.0, start)]

    while pq:
        current_distance, current_node = heapq.heappop(pq)
        if current_node in visited:
            continue

        visited.add(current_node)
        expanded_nodes += 1

        if current_node == end:
            break

        for neighbor, weight in _neighbors_with_cost(graph, current_node):
            if neighbor in visited:
                continue

            new_distance = current_distance + weight
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                came_from[neighbor] = current_node
                heapq.heappush(pq, (new_distance, neighbor))

    path = _reconstruct_path(came_from, start, end)
    if not path:
        return [], float("inf"), expanded_nodes
    return path, distances[end], expanded_nodes


def _heuristic_meters(graph, node_a: int, node_b: int) -> float:
    """Haversine distance in meters between two graph nodes."""
    lat1 = math.radians(graph.nodes[node_a]["y"])
    lon1 = math.radians(graph.nodes[node_a]["x"])
    lat2 = math.radians(graph.nodes[node_b]["y"])
    lon2 = math.radians(graph.nodes[node_b]["x"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    earth_radius_m = 6371000
    return earth_radius_m * c


def astar_search(graph, start: int, end: int) -> Tuple[List[int], float, int]:
    """Return (path, total_distance_m, expanded_nodes)."""
    g_score = {start: 0.0}
    came_from: Dict[int, int] = {}
    visited = set()
    expanded_nodes = 0

    start_f_score = _heuristic_meters(graph, start, end)
    open_set = [(start_f_score, start)]

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue

        visited.add(current)
        expanded_nodes += 1

        if current == end:
            break

        for neighbor, weight in _neighbors_with_cost(graph, current):
            if neighbor in visited:
                continue

            tentative_g = g_score[current] + weight
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + _heuristic_meters(graph, neighbor, end)
                heapq.heappush(open_set, (f_score, neighbor))

    path = _reconstruct_path(came_from, start, end)
    if not path:
        return [], float("inf"), expanded_nodes
    return path, g_score[end], expanded_nodes


def find_route_custom(graph, start: int, end: int, algorithm: str) -> Tuple[List[int], float, int]:
    if algorithm == "A*":
        return astar_search(graph, start, end)
    return dijkstra_search(graph, start, end)


def _straight_line_distance_between_nodes(graph, node_a: int, node_b: int) -> float:
    ax = graph.nodes[node_a]["x"]
    ay = graph.nodes[node_a]["y"]
    bx = graph.nodes[node_b]["x"]
    by = graph.nodes[node_b]["y"]
    return math.hypot(ax - bx, ay - by)


def _select_station_candidates(
    graph,
    start: int,
    end: int,
    station_nodes: List[int],
    max_candidates: int = 12,
) -> List[int]:

    if len(station_nodes) <= max_candidates:
        return station_nodes

    scored = []
    for station in station_nodes:
        d1 = _heuristic_meters(graph, start, station)
        d2 = _heuristic_meters(graph, station, end)

        score = d1 + d2
        scored.append((score, station))

    scored.sort(key=lambda x: x[0])

    return [station for _, station in scored[:max_candidates]]

def _select_nearest_stations(
    graph,
    node: int,
    station_nodes: List[int],
    max_candidates: int = 8,
) -> List[int]:
    scored = []
    for station in station_nodes:
        scored.append((_heuristic_meters(graph, node, station), station))
    scored.sort(key=lambda x: x[0])
    return [station for _, station in scored[:max_candidates]]

def find_route_via_subway_pair(
    graph,
    start: int,
    end: int,
    station_nodes: List[int],
    algorithm: str,
    max_start_candidates: int = 6,
    max_end_candidates: int = 6,
) -> Tuple[List[int], List[int], int, int, float, int, float]:
    """
    Return (path_to_entry, path_from_exit, entry_station, exit_station,
    total_distance_m, expanded_nodes, subway_leg_m)
    """
    if not station_nodes:
        return [], [], -1, -1, float("inf"), 0, 0.0

    start_candidates = _select_nearest_stations(graph, start, station_nodes, max_start_candidates)
    end_candidates = _select_nearest_stations(graph, end, station_nodes, max_end_candidates)

    best_path_to_entry: List[int] = []
    best_path_from_exit: List[int] = []
    best_entry = -1
    best_exit = -1
    best_distance = float("inf")
    best_expanded = 0
    best_subway_leg = 0.0

    for entry_station in start_candidates:
        entry_path, entry_dist, entry_expanded = find_route_custom(graph, start, entry_station, algorithm)
        if not entry_path:
            continue

        for exit_station in end_candidates:
            exit_path, exit_dist, exit_expanded = find_route_custom(graph, exit_station, end, algorithm)
            if not exit_path:
                continue

            subway_leg = _heuristic_meters(graph, entry_station, exit_station)
            total_distance = entry_dist + exit_dist + subway_leg
            total_expanded = entry_expanded + exit_expanded

            if total_distance < best_distance:
                best_distance = total_distance
                best_expanded = total_expanded
                best_path_to_entry = entry_path
                best_path_from_exit = exit_path
                best_entry = entry_station
                best_exit = exit_station
                best_subway_leg = subway_leg

    return (
        best_path_to_entry,
        best_path_from_exit,
        best_entry,
        best_exit,
        best_distance,
        best_expanded,
        best_subway_leg,
    )

def find_route_via_station(
    graph,
    start: int,
    end: int,
    station_nodes: List[int],
    algorithm: str,
    max_candidates: int = 12,
) -> Tuple[List[int], float, int, int]:
    """
    Return (path, total_distance_m, expanded_nodes, chosen_station_node)
    for route constrained to pass at least one station.
    """
    if not station_nodes:
        return [], float("inf"), 0, -1

    candidates = _select_station_candidates(graph, start, end, station_nodes, max_candidates=max_candidates)

    best_path: List[int] = []
    best_distance = float("inf")
    best_expanded = 0
    best_station = -1

    for station in candidates:
        if station == start or station == end:
            continue

        first_path, first_dist, first_expanded = find_route_custom(graph, start, station, algorithm)
        if not first_path:
            continue

        second_path, second_dist, second_expanded = find_route_custom(graph, station, end, algorithm)
        if not second_path:
            continue

        total_dist = first_dist + second_dist
        total_expanded = first_expanded + second_expanded
        merged_path = first_path + second_path[1:]

        if total_dist < best_distance:
            best_distance = total_dist
            best_expanded = total_expanded
            best_path = merged_path
            best_station = station

    if not best_path:
        return [], float("inf"), 0, -1

    return best_path, best_distance, best_expanded, best_station
