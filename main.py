import customtkinter as ctk
from tkintermapview import TkinterMapView
import osmnx as ox
import geopandas as gpd
import pandas as pd
from pathlib import Path
import time
from algorithms import find_route_multimodal_via_rail
from station_store import fetch_station_records_for_place, load_station_records, save_station_records

# Cấu hình giao diện
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
        self.drive_graph_cache_file = "cache/munich_drive.graphml"
        self.rail_graph_cache_file = "cache/munich_rail.graphml"
        self.station_cache_file = "cache/munich_station_nodes_citywide.json"
        self.boundary_cache_file = "cache/munich_neighbor_boundaries.geojson"
        self.boundary_places = [
            "Munich, Bavaria, Germany",
            "Dachau, Bavaria, Germany",
            "Freising, Bavaria, Germany",
            "Erding, Bavaria, Germany",
            "Fürstenfeldbruck, Bavaria, Germany",
            "Starnberg, Bavaria, Germany",
            "Germering, Bavaria, Germany",
            "Ottobrunn, Bavaria, Germany",
            "Unterhaching, Bavaria, Germany",
        ]

        # Khởi tạo dữ liệu
        self.start_node = None
        self.end_node = None
        self.start_marker = None
        self.end_marker = None
        self.path_line = None
        self.station_path_lines = []
        self.station_markers = []  # Markers for boarding/alighting stations in route
        self.all_station_markers = []  # Markers for all available stations
        self.station_records = []
        self.boundary_lines = []
        
        print("Đang tải dữ liệu bản đồ toàn thành phố Munich...")
        self.G_drive = self._load_drive_graph()
        self.G_rail = self._load_rail_graph()
        self._set_map_center_from_graph(self.G_drive)
        print("Tải dữ liệu thành công!")

        print("Đang tải dữ liệu ga tàu Munich...")
        self.station_records = load_station_records(self.station_cache_file)
        if not self.station_records:
            self.station_records = fetch_station_records_for_place(self.G_drive, self.G_rail, self.place_name)
            save_station_records(self.station_records, self.station_cache_file)
        print(f"Đã nạp {len(self.station_records)} ga khả dụng cho tìm đường.")

        # --- LAYOUT ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # 1. Khung bên trái: Bản đồ
        self.map_widget = TkinterMapView(self, corner_radius=0)
        self.map_widget.grid(row=0, column=0, sticky="nsew")
        self.map_widget.set_position(self.center_lat, self.center_lon) # Tọa độ Munich
        self.map_widget.set_zoom(15)

        print("Đang tải ranh giới Munich và các thành phố lân cận...")
        self._draw_neighbor_boundaries()
        print("Đã hiển thị ranh giới hành chính.")

        print("Đang hiển thị tất cả các ga tàu...")
        self._draw_all_stations()
        print("Đã hiển thị các ga tàu.")

        # Chuột phải để chọn điểm
        self.map_widget.add_right_click_menu_command(label="Choose a starting point", command=self.set_start, pass_coords=True)
        self.map_widget.add_right_click_menu_command(label="Choose an ending point", command=self.set_end, pass_coords=True)

        # 2. Khung bên phải: Sidebar điều khiển
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

        # Hiển thị kết quả
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

    def _load_neighbor_boundaries(self):
        cache_path = Path(self.boundary_cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            try:
                return gpd.read_file(cache_path)
            except Exception:
                pass

        rows = []
        for place in self.boundary_places:
            try:
                gdf = ox.geocode_to_gdf(place)
                if gdf.empty:
                    continue
                row = gdf.iloc[[0]].copy()
                row["place_name"] = place
                rows.append(row)
            except Exception as exc:
                print(f"Không thể tải ranh giới cho {place}: {exc}")

        if not rows:
            return gpd.GeoDataFrame()

        merged = gpd.GeoDataFrame(
            pd.concat(rows, ignore_index=True),
            geometry="geometry",
            crs=rows[0].crs,
        )

        try:
            merged.to_file(cache_path, driver="GeoJSON")
        except Exception as exc:
            print(f"Không thể lưu cache ranh giới: {exc}")

        return merged

    def _geometry_to_boundary_paths(self, geometry):
        paths = []
        if geometry is None or geometry.is_empty:
            return paths

        if geometry.geom_type == "Polygon":
            exterior = list(geometry.exterior.coords)
            if exterior:
                paths.append([(lat, lon) for lon, lat in exterior])
            return paths

        if geometry.geom_type == "MultiPolygon":
            for polygon in geometry.geoms:
                exterior = list(polygon.exterior.coords)
                if exterior:
                    paths.append([(lat, lon) for lon, lat in exterior])
            return paths

        return paths

    def _draw_all_stations(self):
        """Display all available train stations on the map."""
        # Clear previous station markers
        for marker in self.all_station_markers:
            marker.delete()
        self.all_station_markers = []

        # Add marker for each station
        for station in self.station_records:
            marker = self.map_widget.set_marker(
                station["lat"],
                station["lon"],
                text=station.get("name", "Station"),
                marker_color_circle="blue",
            )
            self.all_station_markers.append(marker)

    def _draw_neighbor_boundaries(self):
        gdf = self._load_neighbor_boundaries()
        if gdf.empty:
            print("Không có dữ liệu ranh giới để hiển thị.")
            return

        for line in self.boundary_lines:
            line.delete()
        self.boundary_lines = []

        for _, row in gdf.iterrows():
            geometry = row.get("geometry")
            paths = self._geometry_to_boundary_paths(geometry)
            for coords in paths:
                line = self.map_widget.set_path(coords, color="#2e7d32", width=2)
                self.boundary_lines.append(line)

    def _edge_coords(self, graph, u, v):
        """Return edge polyline coords as (lat, lon), following actual road geometry when available."""
        edge_data = graph.get_edge_data(u, v)
        if not edge_data:
            return [(graph.nodes[u]["y"], graph.nodes[u]["x"]), (graph.nodes[v]["y"], graph.nodes[v]["x"])]

        if "length" in edge_data:
            attrs = edge_data
        else:
            attrs = min(edge_data.values(), key=lambda item: float(item.get("length", 1.0)))

        geometry = attrs.get("geometry")
        if geometry is not None:
            coords = [(lat, lon) for lon, lat in geometry.coords]
            if len(coords) >= 2:
                u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
                first = coords[0]
                last = coords[-1]
                d_first = (first[0] - u_lat) ** 2 + (first[1] - u_lon) ** 2
                d_last = (last[0] - u_lat) ** 2 + (last[1] - u_lon) ** 2
                if d_last < d_first:
                    coords.reverse()
                return coords

        return [(graph.nodes[u]["y"], graph.nodes[u]["x"]), (graph.nodes[v]["y"], graph.nodes[v]["x"])]

    def _path_to_map_coords(self, graph, path):
        """Expand node path into a drawable road polyline using edge geometries."""
        if len(path) < 2:
            return [(graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in path]

        route_coords = []
        for idx in range(len(path) - 1):
            u = path[idx]
            v = path[idx + 1]
            segment = self._edge_coords(graph, u, v)

            if not segment:
                continue

            if route_coords and route_coords[-1] == segment[0]:
                route_coords.extend(segment[1:])
            else:
                route_coords.extend(segment)

        return route_coords

    def _load_drive_graph(self):
        cache_path = Path(self.drive_graph_cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            print("Đang đọc drive graph Munich từ cache local...")
            return ox.load_graphml(cache_path)

        print("Không thấy cache graph, đang tải từ OpenStreetMap...")
        graph = ox.graph_from_place(
            self.place_name,
            network_type="drive",
            simplify=True,
            retain_all=False,
        )
        ox.save_graphml(graph, cache_path)
        return graph

    def _load_rail_graph(self):
        cache_path = Path(self.rail_graph_cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            print("Đang đọc rail graph Munich từ cache local...")
            return ox.load_graphml(cache_path)

        print("Không thấy cache rail graph, đang tải từ OpenStreetMap...")
        graph = ox.graph_from_place(
            self.place_name,
            network_type="all",
            custom_filter='["railway"="subway"]',
            simplify=True,
            retain_all=True,
        )
        ox.save_graphml(graph, cache_path)
        return graph

    def _set_map_center_from_graph(self, graph):
        nodes = list(graph.nodes)
        if not nodes:
            return

        sample = nodes[: min(3000, len(nodes))]
        lat_avg = sum(graph.nodes[n]["y"] for n in sample) / len(sample)
        lon_avg = sum(graph.nodes[n]["x"] for n in sample) / len(sample)
        self.center_lat = lat_avg
        self.center_lon = lon_avg

    def set_start(self, coords):
        if self.start_marker: self.start_marker.delete()
        self.start_node = ox.nearest_nodes(self.G_drive, coords[1], coords[0])
        self.start_marker = self.map_widget.set_marker(coords[0], coords[1], text="Start", marker_color_circle="green")

    def set_end(self, coords):
        if self.end_marker: self.end_marker.delete()
        self.end_node = ox.nearest_nodes(self.G_drive, coords[1], coords[0])
        self.end_marker = self.map_widget.set_marker(coords[0], coords[1], text="End", marker_color_circle="red")

    def find_route(self):
        if self.start_node is None or self.end_node is None:
            print("Please select both start and end points!")
            return
        if not self.station_records:
            print("No train station data available in current map area.")
            return

        algo = self.algo_menu.get()
        start_time = time.time()

        try:
            result = find_route_multimodal_via_rail(
                self.G_drive,
                self.G_rail,
                self.start_node,
                self.end_node,
                self.station_records,
                algo,
            )
            if not result:
                raise ValueError("No valid multimodal route found (drive + rail + drive)")

            end_time = time.time()
            distance = result["distance_m"]
            visited_nodes = result["expanded_nodes"]
            board = result["boarding_station"]
            alight = result["alighting_station"]
            drive_start_path = result["drive_start_path"]
            rail_path = result["rail_path"]
            drive_end_path = result["drive_end_path"]
            
            # Cập nhật UI
            self.lbl_dist.configure(text=f"Distance: {distance/1000:.2f} km")
            self.lbl_time.configure(text=f"Time: {(end_time - start_time)*1000:.2f} ms")
            self.lbl_nodes.configure(text=f"Nodes visited: {visited_nodes}")
            self.lbl_station.configure(text="Stations on route: 2 (boarding + alighting)")

            # Xoa ket qua cu
            if self.path_line: self.path_line.delete()
            for line in self.station_path_lines:
                line.delete()
            self.station_path_lines = []
            for marker in self.station_markers:
                marker.delete()
            self.station_markers = []

            # Ve 3 chang: duong bo -> duong tau -> duong bo
            start_coords = self._path_to_map_coords(self.G_drive, drive_start_path)
            rail_coords = self._path_to_map_coords(self.G_rail, rail_path)
            end_coords = self._path_to_map_coords(self.G_drive, drive_end_path)

            line1 = self.map_widget.set_path(start_coords, color="#1f77b4", width=5)
            line2 = self.map_widget.set_path(rail_coords, color="#ff6f00", width=7)
            line3 = self.map_widget.set_path(end_coords, color="#1f77b4", width=5)
            self.station_path_lines.extend([line1, line2, line3])

            board_marker = self.map_widget.set_marker(
                board["lat"],
                board["lon"],
                text="Boarding Station",
                marker_color_circle="#f4b400",
            )
            alight_marker = self.map_widget.set_marker(
                alight["lat"],
                alight["lon"],
                text="Alighting Station",
                marker_color_circle="#fbbc04",
            )
            self.station_markers.extend([board_marker, alight_marker])

        except Exception as e:
            print(f"Cannot find route: {e}")

    def clear_map(self):
        if self.start_marker: self.start_marker.delete()
        if self.end_marker: self.end_marker.delete()
        if self.path_line: self.path_line.delete()
        for line in self.station_path_lines:
            line.delete()
        self.station_path_lines = []
        for marker in self.station_markers:
            marker.delete()
        self.station_markers = []
        self.start_node = self.end_node = None
        self.lbl_dist.configure(text="Distance: N/A")
        self.lbl_nodes.configure(text="Nodes visited: N/A")
        self.lbl_time.configure(text="Time: N/A")
        self.lbl_station.configure(text="Stations on route: N/A")
        # Redraw all station markers
        self._draw_all_stations()

if __name__ == "__main__":
    app = MunichNavigationApp()
    app.mainloop()