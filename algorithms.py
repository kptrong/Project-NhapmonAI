import heapq
import math
from typing import Dict, List, Tuple

# hàm tính độ dài cạnh, hỗ trợ cả Graph và MultiDiGraph của OSMnx
def _edge_length(edge_data: dict) -> float:
    """Return edge length for both Graph and MultiDiGraph adjacency formats."""
    # edge_data là danh sách cạnh (MultiDiGraph) hoặc dict cạnh (Graph)
    # nếu edge_data là đơn cạnh (Graph), trả về độ dài trực tiếp
    if "length" in edge_data:
        return float(edge_data.get("length", 1.0))

    # nếu edge_data là đa cạnh (MultiDiGraph), tìm độ dài nhỏ nhất trong các cạnh
    min_length = float("inf") # khởi tạo với vô cực để tìm min
    for attrs in edge_data.values():
        length = float(attrs.get("length", 1.0))
        if length < min_length:
            min_length = length

    # nếu không tìm thấy độ dài nào, trả về 1.0 làm mặc định
    return min_length if min_length != float("inf") else 1.0

# hàm lấy danh sách hàng xóm kèm chi phí (độ dài) cho một node
def _neighbors_with_cost(graph, node: int) -> List[Tuple[int, float]]:
    # graph lưu trữ các node và cạnh
    neighbors = []
    # graph[node] là một dict chứa các node kề và dữ liệu cạnh 
    for neighbor, edge_data in graph[node].items():
        neighbors.append((neighbor, _edge_length(edge_data)))
    return neighbors

# hàm truy vết đường đi ngắn nhất từ end về start dựa trên came_from
def _reconstruct_path(came_from: Dict[int, int], start: int, end: int) -> List[int]:
    # came_from[i] là node cha của node i trên đường đi ngắn nhất đã tìm được
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

# thuật toán Dijkstra để tìm đường đi ngắn nhất giữa start và end
def dijkstra_search(graph, start: int, end: int) -> Tuple[List[int], float, int]:
    """Return (path, total_distance_m, expanded_nodes)."""
    # distances[node] là khoảng cách ngắn nhất đã biết từ start đến node
    distances = {start: 0.0}
    # came_from[node] là node cha của node trên đường đi ngắn nhất
    came_from: Dict[int, int] = {}
    # visited là tập các node đã được mở rộng để tránh lặp lại
    visited = set()
    # expanded_nodes đếm số node đã được mở rộng trong quá trình tìm kiếm
    expanded_nodes = 0
    # pq là hàng đợi ưu tiên chứa các node chưa được mở rộng, ưu tiên theo khoảng cách ngắn nhất đã biết
    pq = [(0.0, start)]

    while pq:
        current_distance, current_node = heapq.heappop(pq)
        # nếu node đã được mở rộng, bỏ qua
        if current_node in visited:
            continue

        # đánh dấu node hiện tại là đã được mở rộng
        visited.add(current_node)
        expanded_nodes += 1

        # nếu đã đến đích, dừng tìm kiếm
        if current_node == end:
            break

        for neighbor, weight in _neighbors_with_cost(graph, current_node):
            # nếu neighbor đã được mở rộng, bỏ qua
            if neighbor in visited:
                continue

            new_distance = current_distance + weight

            # nếu tìm được đường đi ngắn hơn đến neighbor, cập nhật khoảng cách và node cha
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                came_from[neighbor] = current_node
                heapq.heappush(pq, (new_distance, neighbor))

    path = _reconstruct_path(came_from, start, end)
    if not path:
        return [], float("inf"), expanded_nodes
    return path, distances[end], expanded_nodes

# hàm heuristic cho A* sử dụng khoảng cách Haversine giữa hai node
# Haversine là công thức tính khoảng cách giữa hai điểm trên bề mặt trái đất dựa trên vĩ độ và kinh độ
def _heuristic_meters(graph, node_a: int, node_b: int) -> float:
    """Haversine distance in meters between two graph nodes."""
    # chuyển đổi vĩ độ và kinh độ từ độ sang radian
    #lat1 là vĩ độ của node_a, lon1 là kinh độ của node_a
    lat1 = math.radians(graph.nodes[node_a]["y"])
    lon1 = math.radians(graph.nodes[node_a]["x"])
    #lat2 là vĩ độ của node_b, lon2 là kinh độ của node_b
    lat2 = math.radians(graph.nodes[node_b]["y"])
    lon2 = math.radians(graph.nodes[node_b]["x"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # công thức Haversine: dist = 2 * earth_radius * arcsin(sqrt(sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)))
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    earth_radius_m = 6371000
    return earth_radius_m * c

# thuật toán A* để tìm đường đi ngắn nhất giữa start và end, sử dụng heuristic để ưu tiên các node gần đích hơn
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


def _nearest_station_records(
    graph,
    origin_node: int,
    station_records: List[dict],
    node_key: str,
    max_candidates: int,
) -> List[dict]:
    scored = []
    for record in station_records:
        station_node = record.get(node_key)
        if station_node is None or station_node not in graph.nodes:
            continue

        distance = _straight_line_distance_between_nodes(graph, origin_node, int(station_node))
        scored.append((distance, record))

    scored.sort(key=lambda item: item[0])
    return [record for _, record in scored[:max_candidates]]


def find_route_multimodal_via_rail(
    drive_graph,
    rail_graph,
    start_drive_node: int,
    end_drive_node: int,
    station_records: List[dict],
    algorithm: str,
    start_station_candidates: int = 8,
    end_station_candidates: int = 8,
):
    """
    Find a 3-leg route: drive(start->boarding_station) + rail(boarding->alighting) + drive(alighting->end).
    Return None if no valid route exists.
    """
    if not station_records:
        return None

    # Sort stations by proximity so we can enforce nearest-station-first behavior.
    start_candidates = _nearest_station_records(
        drive_graph,
        start_drive_node,
        station_records,
        node_key="drive_node",
        max_candidates=start_station_candidates,
    )
    end_candidates = _nearest_station_records(
        drive_graph,
        end_drive_node,
        station_records,
        node_key="drive_node",
        max_candidates=end_station_candidates,
    )

    # Keep the best feasible route among nearest-ranked station pairs.
    # Priority order is:
    # 1) nearer boarding station to start
    # 2) nearer alighting station to end
    # 3) shorter total route distance
    best_result = None
    best_rank = None
    best_distance = float("inf")

    for start_rank, board in enumerate(start_candidates):
        for end_rank, alight in enumerate(end_candidates):
            board_drive = int(board["drive_node"])
            board_rail = int(board["rail_node"])
            alight_drive = int(alight["drive_node"])
            alight_rail = int(alight["rail_node"])

            if board_rail == alight_rail:
                continue

            if board_rail not in rail_graph.nodes or alight_rail not in rail_graph.nodes:
                continue

            leg1_path, leg1_dist, leg1_expanded = find_route_custom(
                drive_graph,
                start_drive_node,
                board_drive,
                algorithm,
            )
            if not leg1_path:
                continue

            rail_path, rail_dist, rail_expanded = find_route_custom(
                rail_graph,
                board_rail,
                alight_rail,
                algorithm,
            )
            if not rail_path:
                continue

            leg3_path, leg3_dist, leg3_expanded = find_route_custom(
                drive_graph,
                alight_drive,
                end_drive_node,
                algorithm,
            )
            if not leg3_path:
                continue

            total_distance = leg1_dist + rail_dist + leg3_dist
            total_expanded = leg1_expanded + rail_expanded + leg3_expanded
            pair_rank = (start_rank, end_rank)

            if best_rank is None or pair_rank < best_rank or (pair_rank == best_rank and total_distance < best_distance):
                best_rank = pair_rank
                best_distance = total_distance
                best_result = {
                    "drive_start_path": leg1_path,
                    "rail_path": rail_path,
                    "drive_end_path": leg3_path,
                    "distance_m": total_distance,
                    "expanded_nodes": total_expanded,
                    "boarding_station": board,
                    "alighting_station": alight,
                }

    return best_result
