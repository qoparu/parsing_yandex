import os
import csv
import folium
from folium.plugins import MarkerCluster
import argparse

# --- Настройка ---
parser = argparse.ArgumentParser(description="Генератор карты по логам.")
parser.add_argument("year", type=int, nargs='?', default=None, help="Год для визуализации (например, 2023). Если не указан, будет запрошен.")
args = parser.parse_args()

if args.year:
    YEAR = str(args.year)
else:
    YEAR = input("➡️ Введите год для визуализации (например, 2023): ")
    
if not YEAR.isdigit() or not (2010 < int(YEAR) < 2030):
    print(f"❌ Некорректный год: {YEAR}. Выход.")
    exit()

print(f"🗺️ Генерируем карту для {YEAR} года...")

output_dir = f"output/{YEAR}"
input_csv = "almaty_roads.csv" # Путь к исходному CSV с дорогами
log_file = os.path.join(output_dir, f"metadata_{YEAR}.csv")
bad_addresses_file = os.path.join(output_dir, f"no_panorama_addresses_{YEAR}.csv")
map_output = os.path.join(output_dir, f"map_{YEAR}.html")

# --- Создание карты ---
# Примерный центр для Алматы
map_center = [43.2389, 76.8512] 
road_map = folium.Map(location=map_center, zoom_start=12, tiles='OpenStreetMap')

# --- Нанесение слоев ---
# 1. Базовый слой всех дорог
try:
    with open(input_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        base_roads_layer = folium.FeatureGroup(name="Все дороги (из файла)", show=True).add_to(road_map)
        for row in reader:
            geom = (row.get("geometry_wkt") or "").strip()
            # Простая регулярка для парсинга WKT
            import re
            coords_pairs = re.findall(r"([-\d\.]+)\s+([-\d\.]+)", geom)
            if coords_pairs:
                path = [(float(lat), float(lon)) for lon, lat in coords_pairs]
                folium.PolyLine(path, color="gray", weight=2, opacity=0.7).add_to(base_roads_layer)
    print("✅ Базовый слой дорог нанесен.")
except FileNotFoundError:
    print(f"⚠️ Исходный файл {input_csv} не найден. Базовый слой не будет построен.")

# 2. Маркеры
marker_cluster = MarkerCluster(name=f"Результаты {YEAR}").add_to(road_map)
# Успешные точки
try:
    with open(log_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        success_count = 0
        for row in reader:
            try:
                lat, lon = float(row['Latitude']), float(row['Longitude'])
                popup_text = f"{row.get('RoadName', '')}<br>ObjectID: {row.get('ObjectID', 'N/A')}<br>Статус: Успех"
                folium.Marker(
                    location=[lat, lon], 
                    popup=popup_text, 
                    icon=folium.Icon(color="green", icon="check", prefix='fa')
                ).add_to(marker_cluster)
                success_count += 1
            except (ValueError, KeyError):
                continue
    print(f"✅ Нанесено {success_count} успешных маркеров.")
except FileNotFoundError:
    print(f"ℹ️ Файл лога {os.path.basename(log_file)} не найден.")

# Неудачные точки
try:
    with open(bad_addresses_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        fail_count = 0
        for row in reader:
            try:
                road_name, lat, lon = row[0], float(row[1]), float(row[2])
                popup_text = f"{road_name}<br>Статус: Не найдено"
                folium.Marker(
                    location=[lat, lon], 
                    popup=popup_text, 
                    icon=folium.Icon(color="red", icon="times", prefix='fa')
                ).add_to(marker_cluster)
                fail_count += 1
            except (ValueError, IndexError):
                continue
    print(f"✅ Нанесено {fail_count} маркеров без панорам.")
except FileNotFoundError:
    print(f"ℹ️ Файл лога {os.path.basename(bad_addresses_file)} не найден.")

# --- Сохранение ---
folium.LayerControl().add_to(road_map)
road_map.save(map_output)

print("-" * 50)
print(f"✅ Карта успешно сгенерирована и сохранена: {os.path.abspath(map_output)}")