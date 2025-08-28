# Yandex Panoramas Collector

This project is a Python script for automatically collecting panoramic images from Yandex Maps. It allows for the targeted downloading of images for a given list of geographic coordinates, filtering them by a specific year.

The project is designed to create datasets for computer vision tasks, such as analyzing road conditions, the urban environment, and more.

---

## 🚀 Key Features

* **🎯 Targeted Search by Year:** The script doesn't just find the latest panorama; it searches a location's history to find an image from the specified target year.
* **📍 Geometry-Based Processing:** Operates based on an input `.csv` file containing road geometries, iterating through each coordinate.
* **🔄 Resumable Sessions:** The process can be safely stopped (`Ctrl+C`) and resumed at any time. The script remembers its progress and will not repeat completed work.
* **✂️ Smart Auto-Cropping:** Automatically removes empty black or white borders from older panoramas, saving only the useful portion of the image at its original resolution.
* **✨ Image Deduplication:** Uses perceptual hashing (`imagehash`) to filter out visually identical panoramas, saving storage space and keeping the dataset clean.
* **📈 Sequential & Global Numbering:** Maintains a single global counter for all saved files, ensuring unique image IDs regardless of the processing year.
* **🗺️ Decoupled Visualization:** The data collection and map generation processes are separated into two scripts to ensure stability (due to a library conflict).

---

## 📂 Project Structure

```
.
├── mainn.py                # Main data collection script
├── generate_map.py         # Script to generate the HTML map with results
├── requirements.txt        # List of required Python libraries
├── almaty_roads.csv        # Input file with road geometries
│
├── temp_panoramas/         # Cache of original panoramas (do not delete!)
│   └── *.jpg
│
└── output/
    ├── global_state.pkl    # File with the global ID counter
    └── 2023/               # Folder with results for a specific year
        ├── *.jpg           # Saved and processed panoramas
        ├── metadata_2023.csv # Log of successfully downloaded panoramas
        ├── no_panorama_addresses_2023.csv # Log of points where no panoramas were found
        ├── state.pkl       # State file for resuming sessions
        └── map_2023.html   # HTML map for visualization
```

---

## 🛠️ Installation & Setup

### Requirements
* Python 3.7+
* Libraries listed in `requirements.txt`

### Installation Steps

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/qoparu/parsing_yandex.git
    cd parsing_yandex
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # Create the environment
    python -m venv venv

    # Activate (Windows)
    .\venv\Scripts\activate

    # Activate (macOS/Linux)
    source venv/bin/activate
    ```

3.  **Install all dependencies with a single command:**
    ```bash
    pip install -r requirements.txt
    ```

### Usage

The process is divided into two steps: data collection and map generation.

**Step 1: Data Collection**

Run the main script, passing the desired year as a command-line argument.

```bash
# Example for the year 2017
python mainn.py 2017
```

If the year is not provided, the script will prompt for it interactively. The process can be interrupted at any time (`Ctrl+C`) and restarted—it will resume from where it left off.

**Step 2: Visualizing the Results**

To create an HTML map with markers showing the results of the collection, run the second script.

```bash
# Generate the map for the year 2017
python generate_map.py 2017
```

The generated file, `map_2017.html`, can be opened in any web browser.

---

## 💡 Important Notes

* **Two-Script Architecture:** The separation into `mainn.py` and `generate_map.py` is **necessary** due to a technical conflict between the panorama library (`streetlevel`) and the mapping library (`folium`). Running them in the same process leads to errors.
* **The `temp_panoramas` Cache:** This folder **should not be deleted**. It stores the original downloaded panoramas. This significantly speeds up subsequent runs, as the script does not need to re-download tens of thousands of files.
