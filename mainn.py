import os
import re
import csv
import time
import cv2
import pickle
import argparse
from streetlevel import yandex
from datetime import datetime
from typing import Optional, List
from PIL import Image
import imagehash
import numpy as np
from py360convert import e2p

# ==============================================================================
# КОНФИГУРАЦИЯ
# ==============================================================================
INPUT_CSV = "almaty_roads.csv"
OUTPUT_DIR_BASE = "output"
TEMP_DIR = "temp_panoramas"
TIME_DELAY = 1.0

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def transliterate(string: str) -> str:
    cyrillic_to_latin = {
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E', 'Ж': 'Zh', 'З': 'Z', 'И': 'I',
        'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
        'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y',
        'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya', 'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
        'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh',
        'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
        'я': 'ya', 'Ә': 'A', 'ә': 'a', 'Ғ': 'G', 'ғ': 'g', 'Қ': 'Q', 'қ': 'q', 'Ң': 'N', 'ң': 'n',
        'Ө': 'O', 'ө': 'o', 'Ұ': 'U', 'ұ': 'u', 'Ү': 'U', 'ү': 'u', 'Һ': 'H', 'һ': 'h', 'І': 'I', 'і': 'i'
    }
    return ''.join(cyrillic_to_latin.get(char, char) for char in string)
def fix_encoding(s: str) -> str:
    if not isinstance(s, str) or not s: return s
    try: return s.encode("cp1251").decode("utf-8")
    except Exception: return s
def get_date_from_pano_id(pano_id: str) -> Optional[datetime]:
    parts = pano_id.split("_");
    if not parts: return None
    try:
        return datetime.utcfromtimestamp(int(parts[-1]))
    except (ValueError, IndexError, TypeError):
        return None
def autocrop_image(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, 10, 245)
    coords = cv2.findNonZero(mask)
    if coords is None:
        return img
    x, y, w, h = cv2.boundingRect(coords)
    if w == 0 or h == 0:
        print("   -> Автообрезка дала нулевой размер, используется исходное изображение.")
        return img
    return img[y:y+h, x:x+w]
    
#Функция для нарезки панорамы на виды "вперед" и "назад"
def crop_panorama_to_roi(img: np.ndarray, year: str) -> List[dict]:
    """
    Принимает панораму, нарезает ее на перспективные виды (вперед/назад)
    и возвращает список словарей, каждый из которых содержит вид и его название.
    """
    # Здесь можно хранить профили обрезки для разных лет, как мы делали раньше
    profiles = {
        "default": {"v_deg": -20, "top_frac": 0.5, "end_frac": 1.0, "sub_crop": 0.3},
        "2017": {"v_deg": -7, "top_frac": 0.4, "end_frac": 0.9, "sub_crop": 0.1}
    }
    profile = profiles.get(year, profiles["default"])
    
    output_views = []
    
    for yaw, view_label in [(180, "front"), (0, "back")]:
        view = e2p(img, fov_deg=70, u_deg=yaw, v_deg=profile["v_deg"], out_hw=(1536, 1536))
        h, _, _ = view.shape
        
        top_px = int(h * profile["top_frac"])
        end_px = int(h * profile["end_frac"])
        primary_crop = view[top_px:end_px, :, :]
        
        h_sub, _, _ = primary_crop.shape
        sub_crop_px = int(h_sub * profile["sub_crop"])
        final_crop = primary_crop[sub_crop_px:, :, :]
        
        output_views.append({"label": view_label, "image": final_crop})
        
    return output_views

# ==============================================================================
# ГЛАВНЫЙ СКРИПТ
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Сборщик панорам Яндекс по годам.")
    parser.add_argument("year", type=int, nargs='?', default=None, help="Год для обработки (например, 2023). Если не указан, будет запрошен.")
    args = parser.parse_args()
    if args.year:
        YEAR = str(args.year)
    else:
        YEAR = input("➡️ Введите год для обработки (например, 2023): ")
    if not YEAR.isdigit() or not (2010 < int(YEAR) < 2030):
        print(f"❌ Некорректный год: {YEAR}. Выход."); exit()
    print(f"🚀 Запускаем обработку для {YEAR} года.")
    output_dir = os.path.join(OUTPUT_DIR_BASE, YEAR)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    log_file = os.path.join(output_dir, f"metadata_{YEAR}.csv")
    bad_addresses_file = os.path.join(output_dir, f"no_panorama_addresses_{YEAR}.csv")
    state_path = os.path.join(output_dir, "state.pkl")
    cache_path = os.path.join(TEMP_DIR, "panorama_cache.pkl")
    if not os.path.exists(log_file):
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # NEW ROI: Возвращаем колонку View в лог
            writer.writerow(["ID", "ObjectID", "PanoID", "RoadName", "Latitude", "Longitude", "YearFound", "View", "FilePath", "PanoramaDate"])
    try:
        with open(cache_path, "rb") as f: panorama_cache = pickle.load(f)
    except (FileNotFoundError, EOFError): panorama_cache = {}
    try:
        with open(state_path, "rb") as f: state = pickle.load(f)
        print(f"✅ Загружен файл состояния для {YEAR} года.")
    except (FileNotFoundError, EOFError):
        state = { 'processed_coords': set(), 'image_hashes': set(), 'stats': {'total_duration_seconds': 0.0} }
        print(f"ℹ️ Файл состояния для {YEAR} года не найден, будет создан новый.")
    processed_coords = state['processed_coords']
    image_hashes = state['image_hashes']
    stats = state['stats']
    print(f"-> Обработанных координат: {len(processed_coords)}")
    print(f"-> Уникальных изображений: {len(image_hashes)}")
    logged_pano_ids = set()
    global_id = 0
    try:
        with open(log_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('PanoID'): logged_pano_ids.add(row['PanoID'])
                if row.get('ID') and row['ID'].isdigit():
                    current_id = int(row['ID'])
                    if current_id > global_id: global_id = current_id
        print(f"✅ Найдено {len(logged_pano_ids)} уже обработанных панорам в логе. Начальный ID: {global_id}")
    except FileNotFoundError:
        print("ℹ️ Лог-файл не найден, начинаем с нуля.")
    all_roads_data = []
    with open(INPUT_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name, object_id = (row.get("name") or row.get("name_ru") or "").strip(), row.get("objectid")
            if not raw_name or not object_id: continue
            road_name, geom = fix_encoding(raw_name), (row.get("geometry_wkt") or "").strip()
            coords_pairs = re.findall(r"([-\d\.]+)\s+([-\d\.]+)", geom)
            if not coords_pairs: continue
            path = [(float(lat), float(lon)) for lon, lat in coords_pairs]
            all_roads_data.append({ "name": road_name, "object_id": object_id, "path": path })
    if not all_roads_data:
        print("⚠️ После чтения almaty_roads.csv не найдено ни одного валидного адреса."); exit(1)
    print(f"Найдено {len(all_roads_data)} дорожных сегментов для обработки.")
    print(">>> СТАРТ основного цикла обработки улиц")
    start_time = time.time()
    streets_processed_this_session, coords_processed_this_session = 0, 0
    total_coords_in_file = sum(len(road['path']) for road in all_roads_data)
    try:
        for road in all_roads_data:
            road_name, object_id, segment_path = road['name'], road['object_id'], road['path']
            print(f"\n=================================================")
            print(f"🛣️  Обрабатываем сегмент: «{road_name}» (ObjectID: {object_id})")
            
            sanitized_name = transliterate(road_name).replace(" ", "_").replace("/", "-")
            
            for lat, lon in segment_path:
                if (lat, lon) in processed_coords:
                    continue
                coords_processed_this_session += 1
                print(f"\n📍 Точка: ({lat:.6f}, {lon:.6f}) [{len(processed_coords)}/{total_coords_in_file}]")
                
                pano_to_process = None
                try:
                    time.sleep(TIME_DELAY)
                    latest_pano = yandex.find_panorama(lat, lon)
                    if not latest_pano: raise StopIteration("Панорамы не найдены для этой точки.")
                    all_panos_at_location = [latest_pano] + getattr(latest_pano, 'historical', [])
                    
                    found_pano_for_year = None
                    for pano_candidate in all_panos_at_location:
                        pano_date = getattr(pano_candidate, 'date', None) or get_date_from_pano_id(pano_candidate.id)
                        if pano_date and pano_date.year == int(YEAR):
                            if pano_candidate.id in logged_pano_ids:
                                print(f"   ℹ️ Найдена панорама {YEAR} года ({pano_candidate.id}), но она уже в логе.")
                            else:
                                print(f"   🎯 Найдена панорама за {YEAR} год! ID: {pano_candidate.id}")
                                found_pano_for_year = pano_candidate
                            break 
                    
                    if found_pano_for_year:
                        if getattr(found_pano_for_year, 'image_sizes', None) is None:
                            print(f"   -> Получаем полную информацию для исторической панорамы...")
                            time.sleep(TIME_DELAY) 
                            pano_to_process = yandex.find_panorama_by_id(found_pano_for_year.id)
                        else:
                            pano_to_process = found_pano_for_year
                    else:
                        print(f"   ℹ️ Панорамы за {YEAR} год не найдены для этой точки.")
                except StopIteration as e: print(f"   {e}")
                except Exception as e:
                    if "Expecting value" in str(e): print(f"   ℹ️ API Яндекса вернул некорректный ответ. Пропускаем точку.")
                    else: print(f"   ⚠️ Неожиданная ошибка: {e}")
                
                if pano_to_process and pano_to_process.image_sizes:
                    pano = pano_to_process
                    pano_date = getattr(pano, 'date', None) or get_date_from_pano_id(pano.id)
                    raw_path = os.path.join(TEMP_DIR, f"{pano.id}.jpg")
                    if not os.path.exists(raw_path):
                        print(f"   -> Скачиваем панораму {pano.id}...")
                        yandex.download_panorama(pano, raw_path, zoom=0)
                    
                    img = cv2.imread(raw_path)
                    if img is not None:
                        # NEW ROI: Вызываем новую функцию для нарезки
                        views_to_save = crop_panorama_to_roi(img, YEAR)

                        for view_data in views_to_save:
                            view_label = view_data["label"]
                            view_image = view_data["image"]
                            
                            pil_img = Image.fromarray(cv2.cvtColor(view_image, cv2.COLOR_BGR2RGB))
                            h_hash = imagehash.phash(pil_img)

                            if h_hash in image_hashes:
                                print(f"   ℹ️ Дубликат вида '{view_label}'. Пропускаем.")
                                continue
                            
                            current_id = global_id + 1
                            filename = f"{YEAR}_{current_id:05d}_{sanitized_name}_{view_label}.jpg"
                            filepath = os.path.join(output_dir, filename)
                            
                            if cv2.imwrite(filepath, view_image):
                                global_id = current_id
                                image_hashes.add(h_hash)
                                logged_pano_ids.add(pano.id) # Добавляем основной ID, чтобы не обрабатывать панораму заново
                                with open(log_file, "a", newline="", encoding="utf-8") as f_log:
                                    writer = csv.writer(f_log)
                                    writer.writerow([global_id, object_id, pano.id, road_name, pano.lat, pano.lon, YEAR, view_label, filepath, pano_date.strftime("%Y-%m-%d %H:%M:%S")])
                                print(f"   💾 Сохранен вид '{view_label}': {filepath}")
                    else:
                        print(f"   × Ошибка чтения изображения из кэша: {raw_path}")
                else:
                    with open(bad_addresses_file, "a", newline="", encoding="utf-8") as f_bad:
                        writer = csv.writer(f_bad); writer.writerow([road_name, lat, lon, object_id])
                
                processed_coords.add((lat, lon))
            
            streets_processed_this_session += 1
            print(f"   ✅ Сегмент «{road_name}» (ObjectID: {object_id}) полностью обработан.")
    
    except KeyboardInterrupt:
        print("\n\n❗️ Процесс прерван пользователем.")
    finally:
        # ... (блок finally без изменений) ...
        print("\n>>> ЗАВЕРШЕНИЕ РАБОТЫ...")
        session_duration_seconds = time.time() - start_time
        stats['total_duration_seconds'] += session_duration_seconds
        state['processed_coords'] = processed_coords
        state['image_hashes'] = image_hashes
        state['stats'] = stats
        with open(state_path, "wb") as f_state: pickle.dump(state, f_state)
        with open(cache_path, "wb") as f_cache: pickle.dump(panorama_cache, f_cache)
        print("   -> Финальное состояние сохранено.")
        
        m, s = divmod(session_duration_seconds, 60)
        h, m = divmod(m, 60)
        session_duration_formatted = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
        m_total, s_total = divmod(stats['total_duration_seconds'], 60)
        h_total, m_total = divmod(m_total, 60)
        total_duration_formatted = f"{int(h_total):02d}:{int(m_total):02d}:{int(s_total):02d}"
        print("-" * 50)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"🕒 Время выполнения (сессия): {session_duration_formatted}")
        print(f"🕒 Время выполнения (всего):  {total_duration_formatted}")
        print(f"🛣️  Сегментов обработано (сессия):  {streets_processed_this_session}")
        print(f"📍 Координат (всего):         {len(processed_coords)} / {total_coords_in_file}")
        print(f"🖼️  Сохранено фото (всего):     {global_id}")
        print("-" * 50)
        print(">>> ФИНИШ")


if __name__ == "__main__":
    main()

