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
    """Keep nearest stations to the start-end midpoint to limit route evaluations."""
    if len(station_nodes) <= max_candidates:
        return station_nodes

    mid_x = (graph.nodes[start]["x"] + graph.nodes[end]["x"]) / 2
    mid_y = (graph.nodes[start]["y"] + graph.nodes[end]["y"]) / 2

    scored = []
    for station in station_nodes:
        dx = graph.nodes[station]["x"] - mid_x
        dy = graph.nodes[station]["y"] - mid_y
        scored.append((math.hypot(dx, dy), station))

    scored.sort(key=lambda item: item[0])
    return [station for _, station in scored[:max_candidates]]


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
