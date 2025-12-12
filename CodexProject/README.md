# The Codex Engine (Alpha)

**The Codex Engine** is a procedurally generated Virtual Tabletop (VTT) and Campaign Manager designed for TTRPG Game Masters. 

Unlike traditional VTTs where maps are static images, the Codex Engine uses **fractal generation** and **procedural synthesis**. You can start at the planetary level, zoom into a specific region to generate a local map based on the world terrain, and drill down further into tactical battlemaps for dungeons and buildings.

It features a dual-window system: one control screen for the Game Master and a separate, ray-traced "Fog of War" view for the Players.

## 🌟 Key Features

### 🌍 Fractal World Generation
*   **World Maps:** Generates spherical-mapped worlds using diamond-square algorithms, hydraulic erosion, and thermal erosion simulations.
*   **Fractal Zoom:** When you enter a location on the World Map, the engine takes the pixel data from that region and procedurally upscales it into a high-resolution **Local Map**, maintaining terrain consistency (height, rivers, biomes).

### ⚔️ Tactical Maps & Dungeons
*   **Procedural Layouts:** Generates dungeons using various algorithms (Organic Caverns, Room & Corridor, Mazes).
*   **Blueprint System:** Supports JSON-based blueprints to generate complex structures (e.g., "Ancient Crypt", "Farmstead") with specific layouts and themes.
*   **Dynamic Lighting:** Real-time **Raycasting** engine. 
    *   **Dungeons:** Light stops at walls.
    *   **Outdoor/Geo:** High-ground visibility logic (terrain occludes view based on elevation).

### 🧠 AI Content Generation
*   Integrated with **Google Gemini AI**.
*   Generates context-aware descriptions for rooms, NPCs, rumors, and village lore based on the map data and current campaign theme.

### 🎮 Dual-Window Play
*   **DM Console:** Full control over markers, terrain, vectors, and entity placement.
*   **Player View:** A secondary window (or second monitor) rendering the map from the perspective of the "Party View" marker, applying real-time fog of war and dynamic lighting.

---

## 🛠️ Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/codex-project.git
    cd CodexProject
    ```

2.  **Install Dependencies**
    Ensure you have Python 3.9+ installed.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup AI (Optional)**
    To enable AI text generation features, set your API key as an environment variable:
    *   **Windows:** `set GEMINI_API_KEY=your_api_key_here`
    *   **Mac/Linux:** `export GEMINI_API_KEY=your_api_key_here`

4.  **Run the Engine**
    ```bash
    python main.py
    ```

---

## 🕹️ Controls & Usage

### General Navigation
*   **Left Click + Drag:** Pan the camera.
*   **Mouse Wheel:** Zoom in/out.
*   **Esc:** Go up one map level (e.g., Dungeon -> Local -> World).

### Markers & Interaction
*   **Shift + Left Click:** Create a new Marker (Structure, Dungeon entrance, POI).
*   **Right Click (on Marker):** Open Context Menu (Edit, Delete, Enter).
*   **Left Click (Short):** Enter a marker (transition to the next map layer).

### The "Party View" Marker
To enable the Player Window lighting:
1.  Look for the **Eye Icon** marker (automatically created on maps).
2.  Right-click and select **Edit**.
3.  Ensure `is_active` is checked in the metadata (or click it to toggle state).
4.  Drag this marker to move the players. The Player Window will update in real-time with ray-traced vision.

### Map Editing Tools (Sidebar)
*   **Vectors:** Draw Roads (brown) and Rivers (blue). These persist and influence generation when zooming into Local maps.
*   **Terrain Sliders:** Adjust Sea Level, Light Direction, and Contour intervals in real-time.
*   **Brushes (Tactical):** Paint Walls, Floors, and Void spaces manually.

---

## 📂 Project Structure

*   **`main.py`**: Entry point. Handles the multiprocessing for the Player Window.
*   **`codex_engine/`**: Core logic.
    *   **`controllers/`**: Handles input and rendering logic (`geo_controller` for maps, `tactical_controller` for dungeons).
    *   **`generators/`**: Algorithms for World (erosion), Local (fractal), and Dungeon (rooms) generation.
    *   **`core/`**: Database (`db_manager.py`) and AI (`ai_manager.py`) handling.
    *   **`ui/`**: Pygame UI widgets and renderers.
*   **`data/`**:
    *   **`themes/`**: JSON files defining visual styles (Fantasy, SciFi, Noir, etc.).
    *   **`blueprints/`**: JSON definitions for structures and dungeons.
    *   **`maps/`**: Stores generated PNG heightmaps.
    *   **`codex.db`**: SQLite database storing campaign state.

---

## 🎨 Themes
The engine supports hot-swapping themes. Themes control:
*   Color palettes.
*   Vocabulary (e.g., "Inn" vs "Saloon" vs "Cantina").
*   Generation rules (Forest density, Dungeon algorithms).
*   AI Personality (e.g., "Write like H.P. Lovecraft").

Themes are located in `data/themes/*.json`.

---

## 🔮 Future Roadmap
*   [ ] Weather simulation overlay.
*   [ ] Turn-based combat tracker.
*   [ ] Isometric rendering mode.
*   [ ] Multiplayer network support (Client/Server).

---

## 📄 License
This project is an Alpha prototype. Usage and modification allowed for personal projects.
