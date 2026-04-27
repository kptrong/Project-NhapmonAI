import customtkinter as ctk
from tkintermapview import TkinterMapView
import osmnx as ox
from pathlib import Path
import time
from algorithms import find_route_custom # Đã sửa import
from station_store import fetch_station_nodes_for_place, load_station_nodes, save_station_nodes
import pickle

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
        self.graph_cache_file = "cache/munich_rail.pkl"
        self.station_cache_file = "cache/munich_station_nodes_citywide.json"

        # Khởi tạo dữ liệu
        self.start_node = None
        self.end_node = None
        self.start_marker = None
        self.end_marker = None
        self.path_line = None
        self.station_path_lines = []
        self.station_markers = []
        self.station_nodes = []
        
        print("Đang tải dữ liệu bản đồ toàn thành phố Munich...")
        self.G = self._load_city_graph()
        if self.G:
            self._set_map_center_from_graph()
            print("Tải dữ liệu thành công!")

        print("Đang tải dữ liệu ga tàu Munich...")
        self.station_nodes = load_station_nodes(self.station_cache_file)
        if not self.station_nodes and self.G:
            self.station_nodes = fetch_station_nodes_for_place(self.G, self.place_name)
            save_station_nodes(self.station_nodes, self.station_cache_file)
        print(f"Đã nạp {len(self.station_nodes)} ga khả dụng cho tìm đường.")

        # --- LAYOUT ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # 1. Khung bên trái: Bản đồ
        self.map_widget = TkinterMapView(self, corner_radius=0)
        self.map_widget.grid(row=0, column=0, sticky="nsew")
        self.map_widget.set_position(self.center_lat, self.center_lon) # Tọa độ Munich
        self.map_widget.set_zoom(12) # Zoom out một chút để nhìn rõ đường sắt hơn

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
        
        self.lbl_dist = ctk.CTkLabel(self.result_box, text="Travel Time: N/A", anchor="w")
        self.lbl_dist.pack(fill="x")
        self.lbl_nodes = ctk.CTkLabel(self.result_box, text="Nodes visited: N/A", anchor="w")
        self.lbl_nodes.pack(fill="x")
        self.lbl_time = ctk.CTkLabel(self.result_box, text="Calc Time: N/A", anchor="w")
        self.lbl_time.pack(fill="x")
        self.lbl_station = ctk.CTkLabel(self.result_box, text="Stations on route: N/A", anchor="w")
        self.lbl_station.pack(fill="x")

    def _load_city_graph(self):
        cache_path = Path(self.graph_cache_file)
        
        if cache_path.exists():
            print("Đang đọc mạng lưới đường sắt từ cache PKL siêu tốc...")
            with open(cache_path, "rb") as f:
                return pickle.load(f)

        print("LỖI: Không tìm thấy file cache/munich_rail.pkl!")
        print("Vui lòng chạy lại file preload_data.py để tạo dữ liệu đường sắt.")
        return None

    def _set_map_center_from_graph(self):
        nodes = list(self.G.nodes)
        if not nodes:
            return

        sample = nodes[: min(3000, len(nodes))]
        lat_avg = sum(self.G.nodes[n]["y"] for n in sample) / len(sample)
        lon_avg = sum(self.G.nodes[n]["x"] for n in sample) / len(sample)
        self.center_lat = lat_avg
        self.center_lon = lon_avg

    def set_start(self, coords):
        if not self.G: return
        if self.start_marker: self.start_marker.delete()
        self.start_node = ox.nearest_nodes(self.G, coords[1], coords[0])
        self.start_marker = self.map_widget.set_marker(coords[0], coords[1], text="Start", marker_color_circle="green")

    def set_end(self, coords):
        if not self.G: return
        if self.end_marker: self.end_marker.delete()
        self.end_node = ox.nearest_nodes(self.G, coords[1], coords[0])
        self.end_marker = self.map_widget.set_marker(coords[0], coords[1], text="End", marker_color_circle="red")

    def find_route(self):
        if self.start_node is None or self.end_node is None:
            print("Please select both start and end points!")
            return
        if not self.G:
            print("Graph data is not loaded.")
            return

        algo = self.algo_menu.get()
        start_time = time.time()

        try:
            # Đã sửa: Tìm đường trực tiếp, bỏ qua via_station
            path, distance, visited_nodes = find_route_custom(
                self.G,
                self.start_node,
                self.end_node,
                algo,
            )
            
            if not path:
                raise ValueError("No path found that can pass through a train station")

            end_time = time.time()
            
            # Cập nhật UI
            minutes = distance / 60.0
            self.lbl_dist.configure(text=f"Travel Time: {minutes:.1f} mins")
            self.lbl_time.configure(text=f"Calc Time: {(end_time - start_time)*1000:.2f} ms")
            self.lbl_nodes.configure(text=f"Nodes visited: {visited_nodes}")
            
            station_set = set(self.station_nodes)
            passed_station_nodes = [node for node in path if node in station_set]
            self.lbl_station.configure(text=f"Stations on route: {len(passed_station_nodes)}")

            # Xoa ket qua cu
            if self.path_line: self.path_line.delete()
            for line in self.station_path_lines:
                line.delete()
            self.station_path_lines = []
            for marker in self.station_markers:
                marker.delete()
            self.station_markers = []

            # Ve duong tau mau cam
            path_coords = [(self.G.nodes[n]['y'], self.G.nodes[n]['x']) for n in path]
            self.path_line = self.map_widget.set_path(path_coords, color="#ff6f00", width=6)

            # Danh dau cac ga nam tren tuyen
            for node in passed_station_nodes:
                station_lat = self.G.nodes[node]['y']
                station_lon = self.G.nodes[node]['x']
                marker = self.map_widget.set_marker(
                    station_lat,
                    station_lon,
                    text="Station",
                    marker_color_circle="#1f77b4",
                )
                self.station_markers.append(marker)

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
        self.lbl_dist.configure(text="Travel Time: N/A")
        self.lbl_nodes.configure(text="Nodes visited: N/A")
        self.lbl_time.configure(text="Calc Time: N/A")
        self.lbl_station.configure(text="Stations on route: N/A")

if __name__ == "__main__":
    app = MunichNavigationApp()
    app.mainloop()