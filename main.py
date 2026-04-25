import customtkinter as ctk
from tkintermapview import TkinterMapView
import osmnx as ox
from pathlib import Path
import time
from typing import List, Tuple
from algorithms import find_route_via_station, find_route_via_ubahn
from station_store import (
    fetch_station_mappings_for_place,
    fetch_station_nodes_for_place,
    load_station_mappings,
    load_station_nodes,
    save_station_mappings,
    save_station_nodes,
)

# Cau hinh giao dien
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class MunichNavigationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Munich AI Navigation - Route Via Train Station")
        self.geometry("1200x800")
        self.place_name = "Munich, Bavaria, Germany"
        self.center_lat = 48.1371
        self.center_lon = 11.5754
        self.graph_cache_file = "cache/munich_drive.graphml"
        self.rail_graph_cache_file = "cache/munich_ubahn_rail.graphml"
        self.station_cache_file = "cache/munich_station_nodes_citywide.json"
        self.station_mapping_cache_file = "cache/munich_station_mappings_citywide.json"

        # Khoi tao du lieu
        self.start_node = None
        self.end_node = None
        self.start_marker = None
        self.end_marker = None
        self.path_line = None
        self.rail_path_line = None
        self.station_path_lines = []
        self.station_markers = []
        self.station_nodes = []
        self.station_mappings = []
        
        print("Dang tai du lieu ban do toan thanh pho Munich...")
        self.G = self._load_city_graph()
        self._set_map_center_from_graph()
        print("Tai du lieu thanh cong!")

        print("Dang tai mang ray U-Bahn...")
        self.rail_graph = self._load_ubahn_graph()
        print("Tai mang ray U-Bahn thanh cong!")

        print("Dang tai du lieu ga tau Munich...")
        self.station_nodes = load_station_nodes(self.station_cache_file)
        if not self.station_nodes:
            self.station_nodes = fetch_station_nodes_for_place(self.G, self.place_name)
            save_station_nodes(self.station_nodes, self.station_cache_file)
        print(f"Da nap {len(self.station_nodes)} ga kha dung cho tim duong.")

        print("Dang dong bo mapping ga duong bo <-> ga U-Bahn...")
        self.station_mappings = load_station_mappings(self.station_mapping_cache_file)
        needs_refresh = (not self.station_mappings) or any(
            mapping.get("transfer_total_m", -1.0) < 0
            for mapping in self.station_mappings
        )
        if needs_refresh:
            self.station_mappings = fetch_station_mappings_for_place(self.G, self.rail_graph, self.place_name)
            save_station_mappings(self.station_mappings, self.station_mapping_cache_file)
        print(f"Da nap {len(self.station_mappings)} mapping ga U-Bahn.")

        # --- LAYOUT ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # 1. Khung ben trai: Ban do
        self.map_widget = TkinterMapView(self, corner_radius=0)
        self.map_widget.grid(row=0, column=0, sticky="nsew")
        self.map_widget.set_position(self.center_lat, self.center_lon) # Toa do Munich
        self.map_widget.set_zoom(15)

        # Chuot phai de chon diem
        self.map_widget.add_right_click_menu_command(label="Choose a starting point", command=self.set_start, pass_coords=True)
        self.map_widget.add_right_click_menu_command(label="Choose an ending point", command=self.set_end, pass_coords=True)

        # 2. Khung ben phai: Sidebar dieu khien
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.label_title = ctk.CTkLabel(self.sidebar, text="Find Route", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.pack(pady=20)

        self.algo_label = ctk.CTkLabel(self.sidebar, text="Algorithm:")
        self.algo_label.pack(pady=5)
        self.algo_menu = ctk.CTkOptionMenu(self.sidebar, values=["A*", "Dijkstra"])
        self.algo_menu.pack(pady=10)

        self.btn_search = ctk.CTkButton(self.sidebar, text="Find Route", command=self.find_route, fg_color="#3b8ed0")
        self.btn_search.pack(pady=10)

        self.btn_clear = ctk.CTkButton(self.sidebar, text="Clear Selection", command=self.clear_map, fg_color="#db4437")
        self.btn_clear.pack(pady=10)

        # Hien thi ket qua
        self.result_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.result_box.pack(pady=20, fill="x", padx=10)
        
        self.lbl_dist = ctk.CTkLabel(self.result_box, text="Distance: N/A", anchor="w")
        self.lbl_dist.pack(fill="x")
        self.lbl_nodes = ctk.CTkLabel(self.result_box, text="Nodes visited: N/A", anchor="w")
        self.lbl_nodes.pack(fill="x")
        self.lbl_time = ctk.CTkLabel(self.result_box, text="Time: N/A", anchor="w")
        self.lbl_time.pack(fill="x")
        self.lbl_station = ctk.CTkLabel(self.result_box, text="Stations on route: N/A", anchor="w")
        self.lbl_station.pack(fill="x")

    def _load_city_graph(self):
        cache_path = Path(self.graph_cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            print("Dang doc graph Munich tu cache local...")
            return ox.load_graphml(cache_path)

        print("Khong thay cache graph, dang tai tu OpenStreetMap...")
        graph = ox.graph_from_place(
            self.place_name,
            network_type="drive",
            simplify=True,
            retain_all=False,
        )
        ox.save_graphml(graph, cache_path)
        return graph

    def _load_ubahn_graph(self):
        cache_path = Path(self.rail_graph_cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            print("Dang doc graph U-Bahn tu cache local...")
            return ox.load_graphml(cache_path)

        print("Khong thay cache graph U-Bahn, dang tai tu OpenStreetMap...")
        rail_graph = ox.graph_from_place(
            self.place_name,
            custom_filter='["railway"~"subway|light_rail"]',
            simplify=True,
            retain_all=False,
        )
        ox.save_graphml(rail_graph, cache_path)
        return rail_graph

    def _set_map_center_from_graph(self):
        nodes = list(self.G.nodes)
        if not nodes:
            return

        sample = nodes[: min(3000, len(nodes))]
        lat_avg = sum(self.G.nodes[n]["y"] for n in sample) / len(sample)
        lon_avg = sum(self.G.nodes[n]["x"] for n in sample) / len(sample)
        self.center_lat = lat_avg
        self.center_lon = lon_avg

    def _edge_coords(self, u: int, v: int, graph=None) -> List[Tuple[float, float]]:
        """Return detailed coordinates for edge (u, v), preferring stored geometry."""
        active_graph = graph if graph is not None else self.G
        edge_data = active_graph.get_edge_data(u, v)
        if edge_data is None:
            return [(active_graph.nodes[u]["y"], active_graph.nodes[u]["x"]), (active_graph.nodes[v]["y"], active_graph.nodes[v]["x"])]

        if "geometry" in edge_data:
            geom = edge_data["geometry"]
            return [(lat, lon) for lon, lat in geom.coords]

        best_attrs = None
        best_length = float("inf")
        for attrs in edge_data.values():
            length = float(attrs.get("length", 1.0))
            if length < best_length:
                best_length = length
                best_attrs = attrs

        if best_attrs and "geometry" in best_attrs:
            geom = best_attrs["geometry"]
            return [(lat, lon) for lon, lat in geom.coords]

        return [(active_graph.nodes[u]["y"], active_graph.nodes[u]["x"]), (active_graph.nodes[v]["y"], active_graph.nodes[v]["x"])]

    def _path_to_coords(self, path: List[int], graph=None) -> List[Tuple[float, float]]:
        """Build polyline from edge geometries to avoid straight-line shortcuts."""
        active_graph = graph if graph is not None else self.G
        if not path:
            return []
        if len(path) == 1:
            node = path[0]
            return [(active_graph.nodes[node]["y"], active_graph.nodes[node]["x"])]

        coords: List[Tuple[float, float]] = []
        for i in range(len(path) - 1):
            segment = self._edge_coords(path[i], path[i + 1], graph=active_graph)
            if i > 0 and segment:
                segment = segment[1:]
            coords.extend(segment)
        return coords

    def set_start(self, coords):
        if self.start_marker: self.start_marker.delete()
        self.start_node = ox.nearest_nodes(self.G, coords[1], coords[0])
        self.start_marker = self.map_widget.set_marker(coords[0], coords[1], text="Start", marker_color_circle="green")

    def set_end(self, coords):
        if self.end_marker: self.end_marker.delete()
        self.end_node = ox.nearest_nodes(self.G, coords[1], coords[0])
        self.end_marker = self.map_widget.set_marker(coords[0], coords[1], text="End", marker_color_circle="red")

    def find_route(self):
        if self.start_node is None or self.end_node is None:
            print("Please select both start and end points!")
            return
        if not self.station_nodes:
            print("No train station data available in current map area.")
            return
        if not self.station_mappings:
            print("No U-Bahn station mapping available in current map area.")
            return

        algo = self.algo_menu.get()
        start_time = time.time()

        try:
            road_path_1, rail_path, road_path_2, distance, visited_nodes, entry_station, exit_station = find_route_via_ubahn(
                self.G,
                self.rail_graph,
                self.start_node,
                self.end_node,
                self.station_mappings,
                algo,
            )

            use_ubahn_mode = bool(road_path_1 and rail_path and road_path_2)

            if not use_ubahn_mode:
                path, distance, visited_nodes, station_node = find_route_via_station(
                    self.G,
                    self.start_node,
                    self.end_node,
                    self.station_nodes,
                    algo,
                )
                if not path:
                    raise ValueError("No path found that can pass through a train station")

            end_time = time.time()
            
            # Cap nhat UI
            self.lbl_dist.configure(text=f"Distance: {distance/1000:.2f} km")
            self.lbl_time.configure(text=f"Time: {(end_time - start_time)*1000:.2f} ms")
            self.lbl_nodes.configure(text=f"Nodes visited: {visited_nodes}")
            if use_ubahn_mode:
                self.lbl_station.configure(text=f"Stations on route: {entry_station['name']} -> {exit_station['name']}")
            else:
                station_set = set(self.station_nodes)
                passed_station_nodes = [node for node in path if node in station_set]
                if station_node not in passed_station_nodes:
                    passed_station_nodes.append(station_node)
                self.lbl_station.configure(text=f"Stations on route: {len(passed_station_nodes)}")

            # Xoa ket qua cu
            if self.path_line: self.path_line.delete()
            if self.rail_path_line: self.rail_path_line.delete()
            for line in self.station_path_lines:
                line.delete()
            self.station_path_lines = []
            for marker in self.station_markers:
                marker.delete()
            self.station_markers = []

            if use_ubahn_mode:
                # Ve 2 doan duong bo
                road_1_coords = self._path_to_coords(road_path_1, graph=self.G)
                road_2_coords = self._path_to_coords(road_path_2, graph=self.G)
                self.path_line = self.map_widget.set_path(road_1_coords, color="#1f77b4", width=5)
                if road_2_coords:
                    line = self.map_widget.set_path(road_2_coords, color="#1f77b4", width=5)
                    self.station_path_lines.append(line)

                # Ve doan U-Bahn tren ray co dinh
                rail_coords = self._path_to_coords(rail_path, graph=self.rail_graph)
                self.rail_path_line = self.map_widget.set_path(rail_coords, color="#f4b400", width=7)

                # Ve 2 doan connector chuyen tuyen de tranh dut doan hien thi
                entry_road_coord = (
                    self.G.nodes[entry_station["road_node"]]["y"],
                    self.G.nodes[entry_station["road_node"]]["x"],
                )
                entry_station_coord = (entry_station["lat"], entry_station["lon"])
                entry_rail_coord = (
                    self.rail_graph.nodes[entry_station["rail_node"]]["y"],
                    self.rail_graph.nodes[entry_station["rail_node"]]["x"],
                )
                exit_rail_coord = (
                    self.rail_graph.nodes[exit_station["rail_node"]]["y"],
                    self.rail_graph.nodes[exit_station["rail_node"]]["x"],
                )
                exit_station_coord = (exit_station["lat"], exit_station["lon"])
                exit_road_coord = (
                    self.G.nodes[exit_station["road_node"]]["y"],
                    self.G.nodes[exit_station["road_node"]]["x"],
                )

                transfer_line_1 = self.map_widget.set_path(
                    [entry_road_coord, entry_station_coord, entry_rail_coord],
                    color="#6c757d",
                    width=4,
                )
                transfer_line_2 = self.map_widget.set_path(
                    [exit_rail_coord, exit_station_coord, exit_road_coord],
                    color="#6c757d",
                    width=4,
                )
                self.station_path_lines.append(transfer_line_1)
                self.station_path_lines.append(transfer_line_2)

                # Danh dau ga vao/ga ra
                for station in (entry_station, exit_station):
                    marker = self.map_widget.set_marker(
                        station["lat"],
                        station["lon"],
                        text=station["name"],
                        marker_color_circle="#f4b400",
                    )
                    self.station_markers.append(marker)
            else:
                # Fallback: tuyen duong bo co di qua ga
                path_coords = self._path_to_coords(path, graph=self.G)
                self.path_line = self.map_widget.set_path(path_coords, color="#1f77b4", width=5)

                station_set = set(self.station_nodes)
                station_indices = []
                for idx, node in enumerate(path):
                    if node in station_set:
                        station_indices.append(idx)
                        station_lat = self.G.nodes[node]['y']
                        station_lon = self.G.nodes[node]['x']
                        marker = self.map_widget.set_marker(
                            station_lat,
                            station_lon,
                            text="Station",
                            marker_color_circle="#f4b400",
                        )
                        self.station_markers.append(marker)

                if len(station_indices) >= 2:
                    for i in range(len(station_indices) - 1):
                        left = station_indices[i]
                        right = station_indices[i + 1]
                        if right <= left:
                            continue
                        station_segment = path[left:right + 1]
                        segment_coords = self._path_to_coords(station_segment, graph=self.G)
                        line = self.map_widget.set_path(segment_coords, color="#ff6f00", width=7)
                        self.station_path_lines.append(line)

        except Exception as e:
            print(f"Cannot find route: {e}")

    def clear_map(self):
        if self.start_marker: self.start_marker.delete()
        if self.end_marker: self.end_marker.delete()
        if self.path_line: self.path_line.delete()
        if self.rail_path_line: self.rail_path_line.delete()
        for line in self.station_path_lines:
            line.delete()
        self.station_path_lines = []
        for marker in self.station_markers:
            marker.delete()
        self.station_markers = []
        self.path_line = None
        self.rail_path_line = None
        self.start_node = self.end_node = None
        self.lbl_dist.configure(text="Distance: N/A")
        self.lbl_nodes.configure(text="Nodes visited: N/A")
        self.lbl_time.configure(text="Time: N/A")
        self.lbl_station.configure(text="Stations on route: N/A")

if __name__ == "__main__":
    app = MunichNavigationApp()
    app.mainloop()