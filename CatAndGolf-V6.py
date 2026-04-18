# =========================================================
#  "NEKOLOG-F29" GPSデータ解析プログラム　V6 By Hally
# =========================================================

# -*- coding: utf-8 -*-


import os
import math
import folium
from folium.plugins import HeatMap
import tkinter as tk
from tkinter import messagebox, filedialog
import webbrowser
from datetime import datetime, timedelta
from collections import defaultdict

PARAM_TABLE_TEMPLATE = """
<style>
.container {{
    position: fixed;
    bottom: 10px;
    right: 10px;
    z-index: 900;
    width: 205px;
    background: rgba(255,255,255,0.95);
    border-radius: 4px;
    padding: 8px 10px;
    font-family: "Segoe UI", sans-serif;
    font-size: 12px;
    line-height: 1.4;
    box-shadow: 0 1px 5px rgba(0,0,0,0.4);
}}

.label {{
    font-weight: 600;
}}
</style>

<div class="container">
<div><span class="label">Static Dist : </span> {static_dist}</div>
<div><span class="label">Static Time : </span> {static_time}</div>
<div><span class="label">Lat Scale : </span> {lat_scale}</div>
<div><span class="label">Lon Scale : </span> {lon_scale}</div>
<div><span class="label">Snap Lat : </span> {snap_lat}</div>
<div><span class="label">Snap Lon : </span> {snap_lon}</div>
<br>
<div><span class="label">Speed Limit : </span> {speed_limit}</div>
<div><span class="label">Hdop Limit : </span> {hdop_limit}</div>
<div><span class="label">Jump Limit : </span> {jump_limit}</div>
<div><span class="label">Snap Radius : </span> {snap_radius}</div>
<div><span class="label">Grid Size : </span> {grid_size}</div>
<div><span class="label">Ellipse Ratio : </span> {ellipse_ratio}</div>
<div><span class="label">Line Mode : </span> {line_mode}</div>
<div><span class="label">Log Number : </span> {log_number}</div>
</div>
"""

# =========================================================
#  KML出力
# =========================================================
def export_kml(kml_path, cleaned, segments):
    with open(kml_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        f.write('<Document>\n')
        f.write('<name>NekoLog Track</name>\n')

        # 全体軌跡
        f.write('<Placemark>\n')
        f.write('<name>Full Track</name>\n')
        f.write('<LineString><tessellate>1</tessellate><coordinates>\n')
        for p in cleaned:
            f.write(f'{p["lon"]},{p["lat"]},0\n')
        f.write('</coordinates></LineString>\n')
        f.write('</Placemark>\n')

        # レイヤー別
        for name, idx_s, idx_e, _color in segments:
            if idx_s > idx_e:
                continue
            f.write('<Placemark>\n')
            f.write(f'<name>{name}</name>\n')
            f.write('<LineString><tessellate>1</tessellate><coordinates>\n')
            for i in range(idx_s, idx_e + 1):
                p = cleaned[i]
                f.write(f'{p["lon"]},{p["lat"]},0\n')
            f.write('</coordinates></LineString>\n')
            f.write('</Placemark>\n')

        f.write('</Document>\n')
        f.write('</kml>\n')


# =========================================================
#  F29 ログ → HTML 変換（本体ロジック）
# =========================================================
def convert_f29_log(log_path, params):

    # --- 保存先フォルダ設定 ---
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    save_dir = os.path.join(desktop, "NekoLog_Output")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    import re
    base = os.path.basename(log_path)

    # LOG番号抽出
    m = re.search(r"LOG(\d+)", base.upper())
    log_number = m.group(1).zfill(5) if m else "00000"

    # 作成日時
    now = datetime.now()
    date_part = now.strftime("%m%d")
    time_part = now.strftime("%H%M%S")

    base_name = f"L{log_number}{date_part}{time_part}.html"
    OUTPUT_HTML = os.path.join(save_dir, base_name)

    # パラメータ
    LOG_FILE = log_path

    SPEED_LIMIT_M_PER_S = params['speed_limit']
    HDOP_LIMIT = params['hdop_limit']
    JUMP_FROM_LAST_GOOD_M = params['jump_limit']
    SNAP_RADIUS_M = params['snap_radius']
    GRID_SIZE_M = params['grid_size']
    ELLIPSE_RATIO = params['ellipse_ratio']
    LINE_MODE = params['line_mode']   # "split" or "interpolate"

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # -----------------------------------------------------
    # 全RMC保持（A/V含む） + GGAからHDOP取得
    # -----------------------------------------------------
    rmc_points = []
    hdop_dict = {}
    last_t_local = None

    with open(LOG_FILE, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            if "$GNGGA" in line or "$GPGGA" in line:
                p = line.split(",")
                if len(p) < 10:
                    continue

                raw_time = p[1]
                if raw_time == "":
                    continue

                time_str = raw_time.split(".")[0]

                try:
                    hdop = float(p[8])
                except:
                    hdop = None

                hdop_dict[time_str] = hdop

            if "$GNRMC" in line or "$GPRMC" in line:
                p = line.split(",")
                if len(p) < 10:
                    continue

                status = p[2]  # A or V

                raw_time = p[1]
                if raw_time == "":
                    continue
                time_str = raw_time.split(".")[0]

                raw_date = p[9]
                if len(raw_date) != 6:
                    continue

                try:
                    t = datetime.strptime(raw_date + time_str, "%d%m%y%H%M%S")
                    t_local = t + timedelta(hours=7)
                    if last_t_local is not None and t_local < last_t_local:
                        t_local += timedelta(days=1)
                    last_t_local = t_local
                except:
                    continue

                lat = None
                lon = None

                if status == "A":
                    try:
                        raw_lat = p[3]
                        if raw_lat != "":
                            lat_deg = int(raw_lat[:2])
                            lat_min = float(raw_lat[2:])
                            lat = lat_deg + lat_min / 60.0
                            if p[4] == "S":
                                lat = -lat

                        raw_lon = p[5]
                        if raw_lon != "":
                            lon_deg = int(raw_lon[:3])
                            lon_min = float(raw_lon[3:])
                            lon = lon_deg + lon_min / 60.0
                            if p[6] == "W":
                                lon = -lon
                    except:
                        lat = None
                        lon = None

                hdop = hdop_dict.get(time_str, None)

                rmc_points.append({
                    "lat": lat,
                    "lon": lon,
                    "time": t_local,
                    "time_str": time_str,
                    "hdop": hdop,
                    "status": status
                })

    if not rmc_points:
        raise Exception("RMC データなし")

    rmc_points.sort(key=lambda x: x["time"])

    # -----------------------------------------------------
    # 最初のRMC(A) ～ 最後のRMC(A) の範囲抽出
    # -----------------------------------------------------
    first_idx = next((i for i, p in enumerate(rmc_points) if p["status"] == "A" and p["lat"] is not None and p["lon"] is not None), None)
    last_idx  = next((i for i in reversed(range(len(rmc_points))) if rmc_points[i]["status"] == "A" and rmc_points[i]["lat"] is not None and rmc_points[i]["lon"] is not None), None)

    if first_idx is None or last_idx is None:
        raise Exception("有効RMCなし")

    rmc_points = rmc_points[first_idx:last_idx + 1]

    valid_source = [p for p in rmc_points if p["status"] == "A" and p["lat"] is not None and p["lon"] is not None]
    if not valid_source:
        raise Exception("有効RMCなし")

    session_start_time = valid_source[0]["time"]

    # -----------------------------------------------------
    # 既存ロジック維持：Aのみをフィルタ対象
    # -----------------------------------------------------
    valid = []
    first = valid_source[0]

    if first["hdop"] is None or first["hdop"] <= HDOP_LIMIT:
        valid.append(first)
        last_good = first
    else:
        last_good = None

    for p in valid_source[1:]:
        if p["hdop"] is not None and p["hdop"] > HDOP_LIMIT:
            continue

        if last_good is None:
            valid.append(p)
            last_good = p
            continue

        dt = (p["time"] - last_good["time"]).total_seconds()

        # ★ ギャップ検出（ここが核心）
        if dt > 120:   # ← 2分以上途切れたら別セッション扱い
            valid.append(p)
            last_good = p
            continue
 
        dist = haversine(last_good["lat"], last_good["lon"], p["lat"], p["lon"])
        speed = dist / dt

        if dist > JUMP_FROM_LAST_GOOD_M:
            continue
        if speed > SPEED_LIMIT_M_PER_S:
            continue

        valid.append(p)
        last_good = p

    if not valid:
        raise Exception("フィルタリング後の有効データがありません")

    cleaned = valid

    # -----------------------------------------------------
    # 既存ロジック維持 + ELLIPSE_RATIO追加
    # -----------------------------------------------------
    STATIC_DIST_M = params['static_dist']
    STATIC_TIME_S = params['static_time']
    LAT_SCALE = params['lat_scale']
    LON_SCALE = params['lon_scale']
    STATIC_SNAP_LAT = params['snap_lat']
    STATIC_SNAP_LON = params['snap_lon']


    # =========================
    # 静止検出
    # =========================
    STATIC_RADIUS_M = STATIC_DIST_M


    def detect_static_clusters(points):
        clusters = []
        cluster = [points[0]]

        for p in points[1:]:
            dist = haversine(cluster[0]["lat"], cluster[0]["lon"], p["lat"], p["lon"])

            if dist <= STATIC_RADIUS_M:
                cluster.append(p)
            else:
                dt = (cluster[-1]["time"] - cluster[0]["time"]).total_seconds()
                if dt >= STATIC_TIME_S:
                    clusters.append(cluster)
                else:
                    clusters.extend([[x] for x in cluster])

                cluster = [p]

        if cluster:
            dt = (cluster[-1]["time"] - cluster[0]["time"]).total_seconds()
            if dt >= STATIC_TIME_S:
                clusters.append(cluster)
            else:
                clusters.extend([[x] for x in cluster])

        return clusters


    def collapse_clusters(clusters):
        result = []

        for cl in clusters:
            if len(cl) == 1:
                result.append(cl[0])
                continue

            # --- 基準点（最初の位置） ---
            base_lat = cl[0]["lat"]
            base_lon = cl[0]["lon"]

            # --- 中央値 ---
            lats = sorted(p["lat"] for p in cl)
            lons = sorted(p["lon"] for p in cl)
            med_lat = lats[len(lats)//2]
            med_lon = lons[len(lons)//2]

            # --- 距離差で採用判断 ---
            if haversine(base_lat, base_lon, med_lat, med_lon) < 10:
                lat = med_lat
                lon = med_lon
            else:
                lat = base_lat
                lon = base_lon
            # ▲▲▲ ここまで ▲▲▲

            result.append({
                "lat": lat,
                "lon": lon,
                "time": cl[0]["time"],
                "time_str": cl[0].get("time_str"),
                "hdop": cl[0].get("hdop"),
                "status": "A"
            })

        return result
    optimized = []
    cluster = []

    def ellip_dist(p1, p2):
        dlat = haversine(p1["lat"], p1["lon"], p2["lat"], p1["lon"])
        dlon = haversine(p1["lat"], p1["lon"], p1["lat"], p2["lon"])
        return (dlat / LAT_SCALE) ** 2 + ((dlon * ELLIPSE_RATIO) / LON_SCALE) ** 2

    def weighted_avg(points):
        if not points:
            return None
        center = points[len(points) // 2]
        weights = []
        for p in points:
            d = ellip_dist(center, p)
            w = 1 / (1 + d)
            weights.append(w)

        total_w = sum(weights)
        lat = sum(p["lat"] * w for p, w in zip(points, weights)) / total_w
        lon = sum(p["lon"] * w for p, w in zip(points, weights)) / total_w
        t = points[0]["time"]

        return {
            "lat": lat,
            "lon": lon,
            "time": t,
            "time_str": points[0].get("time_str", ""),
            "hdop": points[0].get("hdop"),
            "status": "A"
        }

    last = cleaned[0]
    optimized.append(last)

    for p in cleaned[1:]:
        dt = (p["time"] - last["time"]).total_seconds()
        dist = haversine(last["lat"], last["lon"], p["lat"], p["lon"])

        if dt <= STATIC_TIME_S and dist <= STATIC_DIST_M:
            cluster.append(p)
            continue

        if cluster:
            cluster.append(last)
            avg_p = weighted_avg(cluster)
            if avg_p is not None:
                optimized.append(avg_p)
            cluster = []

        dlat = haversine(last["lat"], last["lon"], p["lat"], last["lon"])
        dlon = haversine(last["lat"], last["lon"], last["lat"], p["lon"])

        if dlat < STATIC_SNAP_LAT and dlon < STATIC_SNAP_LON:
            continue

        optimized.append(p)
        last = p

    if cluster:
        cluster.append(last)
        avg_p = weighted_avg(cluster)
        if avg_p is not None:
            optimized.append(avg_p)

    cleaned = optimized

    # -----------------------------------------------------
    # 既存スナップ
    # -----------------------------------------------------
    snapped = []
    last = None

    for p in cleaned:
        if last is None:
            snapped.append(p)
            last = p
            continue

        dist = haversine(last["lat"], last["lon"], p["lat"], p["lon"])
        if dist < SNAP_RADIUS_M:
            continue

        snapped.append(p)
        last = p

    cleaned = snapped

    # -----------------------------------------------------
    # 既存スムージング
    # -----------------------------------------------------
    smoothed = []
    N = len(cleaned)

    for i in range(N):
        if i < 2 or i > N - 3:
            smoothed.append(cleaned[i])
            continue

        lat = (
            cleaned[i - 2]["lat"] + cleaned[i - 1]["lat"] + cleaned[i]["lat"] +
            cleaned[i + 1]["lat"] + cleaned[i + 2]["lat"]
        ) / 5

        lon = (
            cleaned[i - 2]["lon"] + cleaned[i - 1]["lon"] + cleaned[i]["lon"] +
            cleaned[i + 1]["lon"] + cleaned[i + 2]["lon"]
        ) / 5

        p = cleaned[i].copy()
        p["lat"] = lat
        p["lon"] = lon
        smoothed.append(p)

    cleaned = smoothed
    clusters = detect_static_clusters(cleaned)
    cleaned = collapse_clusters(clusters)

    for idx, p in enumerate(cleaned):
        p["sec_index"] = idx
        p["sec_time"] = session_start_time + timedelta(seconds=idx)

    def grid_key(lat, lon):
        x = int(lat * 111320 / GRID_SIZE_M)
        y = int(lon * 111320 * math.cos(math.radians(lat)) / GRID_SIZE_M)
        return (x, y)

    # -----------------------------------------------------
    # ヒートマップ
    # -----------------------------------------------------
    grid = defaultdict(float)

    for i in range(1, len(cleaned)):
        dt = (cleaned[i]["time"] - cleaned[i - 1]["time"]).total_seconds()
        if dt <= 0:
            continue
        key = grid_key(cleaned[i]["lat"], cleaned[i]["lon"])
        grid[key] += dt

    heat_data = []
    for (x, y), weight in grid.items():
        lat = (x * GRID_SIZE_M) / 111320
        lon = (y * GRID_SIZE_M) / (111320 * math.cos(math.radians(lat)))
        heat_data.append([lat, lon, weight])

    total_pts = len(cleaned)
    if total_pts == 0:
        raise Exception("有効なポイントがありません")

    # -----------------------------------------------------
    # 8レイヤー分割（現行維持）
    # -----------------------------------------------------
    colors = [
        ("#99ccff", "#0066cc"),
        ("#99ff99", "#009933"),
        ("#ffff99", "#cccc00"),
        ("#ff9999", "#cc0000"),
    ]

    layer_defs = []

    for i in range(4):
        idx_start = int(total_pts * i / 4)
        idx_end = int(total_pts * (i + 1) / 4) - 1

        if idx_end >= idx_start:
            idx_mid = idx_start + (idx_end - idx_start) // 2
            start_str = cleaned[idx_start]["time"].strftime("%H:%M")
            mid_str = cleaned[idx_mid]["time"].strftime("%H:%M")
            end_str = cleaned[idx_end]["time"].strftime("%H:%M")

            layer_defs.append((f"Page{i+1} 前半  {start_str}〜{mid_str}", idx_start, idx_mid, colors[i][0]))
            layer_defs.append((f"Page{i+1} 後半  {mid_str}〜{end_str}", idx_mid + 1, idx_end, colors[i][1]))

    # -----------------------------------------------------
    # 地図作成
    # -----------------------------------------------------
    center_lat = cleaned[0]["lat"]
    center_lon = cleaned[0]["lon"]

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=19,
        max_zoom=22,
        tiles=None
    )

    date_str = cleaned[0]["time"].strftime("%Y-%m-%d")
    folium.FeatureGroup(name=f"📅 {date_str}").add_to(m)

    folium.TileLayer(
        tiles="CartoDB Positron",
        name="白地図（CartoDB）",
        max_zoom=22,
        maxNativeZoom=19
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google 衛星写真",
        max_zoom=22,
        maxNativeZoom=20,
        no_wrap=True
    ).add_to(m)

    folium.raster_layers.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="衛星写真（Esri）",
        max_zoom=22,
        maxNativeZoom=19
    ).add_to(m)

    # -----------------------------------------------------
    # 不成立区間判定
    # A以外が挟まっていたら split時に切る
    # -----------------------------------------------------
    def has_invalid_gap(t1, t2):
        start_t = min(t1, t2)
        end_t = max(t1, t2)

        found_inside = False
        for p in rmc_points:
            if start_t < p["time"] < end_t:
                found_inside = True
                if p["status"] != "A" or p["lat"] is None or p["lon"] is None:
                    return True
        return False if found_inside else False

    def build_segment_lines(point_list):
        if not point_list:
            return []

        if LINE_MODE == "interpolate":
            return [[(p["lat"], p["lon"]) for p in point_list]]

        # split
        lines = []
        current = [(point_list[0]["lat"], point_list[0]["lon"])]

        for prev, curr in zip(point_list[:-1], point_list[1:]):
            if has_invalid_gap(prev["time"], curr["time"]):
                if len(current) >= 2:
                    lines.append(current)
                current = [(curr["lat"], curr["lon"])]
            else:
                current.append((curr["lat"], curr["lon"]))

        if len(current) >= 2:
            lines.append(current)

        return lines

    # -----------------------------------------------------
    # レイヤー描画
    # -----------------------------------------------------
    for name, idx_s, idx_e, color in layer_defs:
        layer_points = [p for p in cleaned if idx_s <= p["sec_index"] <= idx_e]
        if len(layer_points) >= 1:
            fg = folium.FeatureGroup(name=name)
            line_groups = build_segment_lines(layer_points)

            for seg in line_groups:
                if len(seg) >= 2:
                    folium.PolyLine(
                        locations=seg,
                        color=color,
                        weight=4,
                        opacity=0.9
                    ).add_to(fg)

            fg.add_to(m)

    # -----------------------------------------------------
    # 全体軌跡ライン
    # -----------------------------------------------------
    full_fg = folium.FeatureGroup(name="移動軌跡ライン")
    full_lines = build_segment_lines(cleaned)

    for seg in full_lines:
        if len(seg) >= 2:
            folium.PolyLine(
                locations=seg,
                color="cyan",
                weight=4,
                opacity=0.9
            ).add_to(full_fg)

    full_fg.add_to(m)

    if heat_data:
        HeatMap(
            heat_data,
            name="滞在ヒートマップ",
            min_opacity=0.4,
            radius=12,
            blur=15,
            max_zoom=22
        ).add_to(folium.FeatureGroup(name="滞在ヒートマップ").add_to(m))

    folium.LayerControl(collapsed=False).add_to(m)

    # HTML保存
    m.save(OUTPUT_HTML)

    # -----------------------------------------------------
    # パラメータ表埋め込み
    # -----------------------------------------------------
    with open(OUTPUT_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    base = os.path.basename(log_path)
    pure_log_number = "".join([c for c in base if c.isdigit()])

    table_html = PARAM_TABLE_TEMPLATE.format(
        static_dist=params['static_dist'],
        static_time=params['static_time'],
        lat_scale=params['lat_scale'],
        lon_scale=params['lon_scale'],
        snap_lat=params['snap_lat'],
        snap_lon=params['snap_lon'],
        speed_limit=params['speed_limit'],
        hdop_limit=params['hdop_limit'],
        jump_limit=params['jump_limit'],
        snap_radius=params['snap_radius'],
        grid_size=params['grid_size'],
        ellipse_ratio=params['ellipse_ratio'],
        line_mode=params['line_mode'],
        log_number=pure_log_number
    )



    insert_pos = html.find('<div class="folium-map"')
    if insert_pos != -1:
        insert_pos = html.find(">", insert_pos) + 1
        new_html = html[:insert_pos] + table_html + html[insert_pos:]
    else:
        new_html = html + table_html

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    # -----------------------------------------------------
    # KML出力
    # -----------------------------------------------------
    kml_path = OUTPUT_HTML.replace(".html", ".kml")
    export_kml(kml_path, cleaned, layer_defs)

    return OUTPUT_HTML


# =========================================================
#  Chrome で HTML を開く
# =========================================================
def open_in_chrome(html_path):
    try:
        chrome = webbrowser.get("chrome")
        chrome.open_new_tab(html_path)
    except:
        webbrowser.open_new_tab(html_path)


# =========================================================
#  SDカードの自動検出
# =========================================================
def find_sdcard():
    for drive in "DEFGHIJKLMNOPQRSTUVWXYZ":
        path = f"{drive}:/"
        if os.path.exists(path):
            try:
                files = [
                    f for f in os.listdir(path)
                    if os.path.isfile(os.path.join(path, f))
                    and f.upper().startswith("LOG")
                    and f.upper().endswith(".TXT")
                ]
                if files:
                    return path
            except:
                continue
    return None


def load_logs_from(path):
    try:
        files = [
            f for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
            and f.upper().startswith("LOG")
            and f.upper().endswith(".TXT")
        ]
        files.sort(reverse=True)
        return files
    except:
        return []


# =========================================================
#  GUI 本体
# =========================================================
class F29GUI:
    def __init__(self, root):
        self.root = root
        root.title("NekoLog F29 – Config & Select")
        root.geometry("640x600")
        root.resizable(False, False)

        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

        config_frame = tk.LabelFrame(root, text=" Parameter Settings ", padx=10, pady=10)
        config_frame.pack(fill="x", padx=10, pady=5)

        # プロファイル
        self.preset_var = tk.StringVar(value="Cat_BN180")
        tk.Radiobutton(config_frame, text="GPS MID size (BN-180)", variable=self.preset_var, value="Cat_BN180", command=self.apply_preset).grid(row=0, column=0, sticky="w")
        tk.Radiobutton(config_frame, text="GPS Small size (BE-122)", variable=self.preset_var, value="Cat_BE122", command=self.apply_preset).grid(row=0, column=1, sticky="w")
        tk.Radiobutton(config_frame, text="Golf log SP", variable=self.preset_var, value="Golf", command=self.apply_preset).grid(row=0, column=2, sticky="w")
        tk.Radiobutton(config_frame, text="Drive log SP", variable=self.preset_var, value="Drive", command=self.apply_preset).grid(row=0, column=3, sticky="w")

        self.entries = {}

        left_labels = [
            ("static_dist", "STATIC_DIST"),
            ("static_time", "STATIC_TIME"),
            ("lat_scale",   "LAT_SCALE"),
            ("lon_scale",   "LON_SCALE"),
            ("snap_lat",    "SNAP_LAT"),
            ("snap_lon",    "SNAP_LON")
        ]

        right_labels = [
            ("speed",   "SPEED_LIMIT (m/s)"),
            ("hdop",    "HDOP_LIMIT"),
            ("jump",    "JUMP_LIMIT (m)"),
            ("snap",    "SNAP_RADIUS (m)"),
            ("grid",    "GRID_SIZE (m)"),
            ("ellipse", "ELLIPSE_RATIO")
        ]

        ranges = {
            "static_dist": "0 – 100",
            "static_time": "1 – 500",
            "lat_scale":   "0 – 100",
            "lon_scale":   "0 – 100",
            "snap_lat":    "0 – 100",
            "snap_lon":    "0 – 100",
            "speed":       "0 – 100",
            "hdop":        "1 – 50",
            "jump":        "0 – 10000",
            "snap":        "0 – 100",
            "grid":        "1 – 1000",
            "ellipse":     "0.5 – 3.0"
        }

        params_row = tk.Frame(config_frame)
        params_row.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 2))

        left_frame = tk.Frame(params_row)
        left_frame.pack(side="left", anchor="n")

        right_frame = tk.Frame(params_row)
        right_frame.pack(side="left", anchor="n", padx=(18, 0))

        for i, (key, label) in enumerate(left_labels):
            tk.Label(left_frame, text=label, width=12, anchor="e").grid(row=i, column=0, sticky="e", pady=2)

            ent = tk.Entry(left_frame, width=8)
            ent.grid(row=i, column=1, sticky="w", padx=(6, 6))
            self.entries[key] = ent

            tk.Label(left_frame, text=ranges[key], fg="gray", width=8, anchor="w").grid(row=i, column=2, sticky="w")

        for i, (key, label) in enumerate(right_labels):
            tk.Label(right_frame, text=label, width=16, anchor="e").grid(row=i, column=0, sticky="e", pady=2)

            ent = tk.Entry(right_frame, width=8)
            ent.grid(row=i, column=1, sticky="w", padx=(6, 6))
            self.entries[key] = ent

            tk.Label(right_frame, text=ranges[key], fg="gray", width=10, anchor="w").grid(row=i, column=2, sticky="w")

        tk.Label(config_frame, text="LINE_MODE").grid(row=2, column=0, sticky="e", pady=6)
        self.line_mode_var = tk.StringVar(value="split")
        line_mode_frame = tk.Frame(config_frame)
        line_mode_frame.grid(row=2, column=1, columnspan=3, sticky="w")
        tk.Radiobutton(line_mode_frame, text="Split", variable=self.line_mode_var, value="split").pack(side="left")
        tk.Radiobutton(line_mode_frame, text="Interpolate", variable=self.line_mode_var, value="interpolate").pack(side="left", padx=10)


        self.apply_preset()

        data_frame = tk.LabelFrame(root, text=" Data Selection ", padx=10, pady=10)
        data_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        button_row = tk.Frame(data_frame)
        button_row.pack(fill="x", pady=(0, 5))

        font_common = ("Segoe UI", 16)

        self.btn_select = tk.Button(
            button_row,
            text="Select Data Folder",
            bg="#d0e4ff",
            font=font_common,
            command=self.select_folder
        )
        self.btn_select.pack(side="left", padx=5)

        self.btn_open = tk.Button(
            button_row,
            text="Map Display",
            bg="#4caf50",
            fg="white",
            font=font_common,
            command=self.open_selected
        )
        self.btn_open.pack(side="left", padx=5)

        list_frame = tk.Frame(data_frame)
        list_frame.pack(fill="both", expand=True)

        self.scroll = tk.Scrollbar(list_frame)
        self.scroll.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=self.scroll.set,
            selectmode="single",
            font=("Segoe UI Emoji", 10)
        )
        self.listbox.pack(fill="both", expand=True)

        self.scroll.config(command=self.listbox.yview)

        self.current_path = None
        self.auto_load_sdcard()

    def apply_preset(self):
        presets = {
            "Cat_BN180": {
                "static_dist": "2.0",
                "static_time": "10",
                "lat_scale": "4.0",
                "lon_scale": "2.0",
                "snap_lat": "5.0",
                "snap_lon": "2.0",
                "speed": "3.0",
                "hdop": "3.0",
                "jump": "10",
                "snap": "3",
                "grid": "1",
                "ellipse": "1.0"
            },
            "Cat_BE122": {
                "static_dist": "2.0",
                "static_time": "10",
                "lat_scale": "4.0",
                "lon_scale": "2.0",
                "snap_lat": "5.0",
                "snap_lon": "2.0",
                "speed": "3.0",
                "hdop": "4.0",
                "jump": "15",
                "snap": "4",
                "grid": "1",
                "ellipse": "1.4"
            },
            "Golf": {
                "static_dist": "2.0",
                "static_time": "10",
                "lat_scale": "4.0",
                "lon_scale": "2.0",
                "snap_lat": "5.0",
                "snap_lon": "2.0",
                "speed": "10.0",
                "hdop": "2.5",
                "jump": "50",
                "snap": "5",
                "grid": "1",
                "ellipse": "1.0"
            },
            "Drive": {
                "static_dist": "2.0",
                "static_time": "10",
                "lat_scale": "4.0",
                "lon_scale": "2.0",
                "snap_lat": "5.0",
                "snap_lon": "2.0",
                "speed": "100",
                "hdop": "3.0",
                "jump": "100",
                "snap": "4",
                "grid": "1",
                "ellipse": "1.0"
            }
        }

        p = presets[self.preset_var.get()]
        for key, val in p.items():
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, val)



    def count_rmc(self, filepath):
        count = 0
        try:
            with open(filepath, "r", errors="ignore") as f:
                for line in f:
                    if line.startswith("$GPRMC") or line.startswith("$GNRMC"):
                        count += 1
        except:
            pass
        return count

    def get_params(self):
        try:
            return {
                'static_dist': float(self.entries['static_dist'].get()),
                'static_time': float(self.entries['static_time'].get()),
                'lat_scale': float(self.entries['lat_scale'].get()),
                'lon_scale': float(self.entries['lon_scale'].get()),
                'snap_lat': float(self.entries['snap_lat'].get()),
                'snap_lon': float(self.entries['snap_lon'].get()),
                'speed_limit': float(self.entries['speed'].get()),
                'hdop_limit': float(self.entries['hdop'].get()),
                'jump_limit': float(self.entries['jump'].get()),
                'snap_radius': float(self.entries['snap'].get()),
                'grid_size': float(self.entries['grid'].get()),
                'ellipse_ratio': float(self.entries['ellipse'].get()),
                'line_mode': self.line_mode_var.get()
            }
        except ValueError:
            messagebox.showerror("Error", "パラメータには数値を入力してください")
            return None

    def auto_load_sdcard(self):
        sd = find_sdcard()
        if sd is None:
            return
        self.current_path = sd
        self.load_list(sd)

    def select_folder(self):
        path = filedialog.askdirectory()
        if not path:
            return
        self.current_path = path
        self.load_list(path)

    def analyze_log_file(self, path):
        size_kb = os.path.getsize(path) // 1024
        rmc = False

        try:
            with open(path, "r", errors="ignore") as f:
                for _ in range(200):
                    line = f.readline()
                    if not line:
                        break
                    if "RMC" in line:
                        rmc = True
                        break
        except:
            pass

    def load_list(self, path):
        self.listbox.delete(0, tk.END)
        logs = load_logs_from(path)

        if not logs:
            messagebox.showwarning("Warning", "選択されたフォルダにLOG*.TXTが見つかりません")

        for f in logs:
            full = os.path.join(path, f)
            try:
                rmc = False
                with open(full, "r", errors="ignore") as fp:
                    for line in fp:
                        if line.startswith("$") and "RMC" in line:
                            parts = line.split(",")
                            if len(parts) > 2 and parts[2] == "A":
                                rmc = True
                                break
                mark = "◎" if rmc else "×"
            except:
                mark = "○"

            size = os.path.getsize(full) // 1024
            rmc_count = self.count_rmc(full)

            # 1s換算
            m_1s, _ = divmod(rmc_count, 60)
            h_1s, m_1s = divmod(m_1s, 60)

            # 5s換算
            m_5s, _ = divmod(rmc_count * 5, 60)
            h_5s, m_5s = divmod(m_5s, 60)

            time_info = f"1s:{h_1s}h{m_1s}m / 5s:{h_5s}h{m_5s}m"
            text = f"{f:<15}  {size:>5}kb   {mark}   ({rmc_count} / {time_info})"

            self.listbox.insert(tk.END, text)

    def open_selected(self):
        params = self.get_params()
        if params is None:
            return

        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "ログが選択されていません")
            return

        filename = self.listbox.get(sel[0]).split()[0]
        log_path = os.path.join(self.current_path, filename)

        try:
            html = convert_f29_log(log_path, params)
            open_in_chrome(html)
        except Exception as e:
            messagebox.showerror("Error", f"変換に失敗しました:\n{e}")


# =========================================================
#  実行
# =========================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = F29GUI(root)
    root.mainloop()