import json
import random
import os
from codex_engine.config import DATA_DIR

class BuildingGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.bp_path = DATA_DIR / "blueprints"

    def generate(self, parent_node, marker, campaign_id):
        bp_id = marker.get('blueprint_id')
        blueprint = self._load_blueprint(bp_id)
        if not blueprint: return None

        # Whether it's a 'compound' or 'structure' blueprint, we treat them as a collection of floors
        # parented to the Local Map.
        return self._generate_complex(blueprint, parent_node, marker, campaign_id)

    def _load_blueprint(self, bp_id):
        for cat in ["complexes", "definitions"]:
            path = self.bp_path / "structures" / cat / f"{bp_id}.json"
            if path.exists():
                with open(path, 'r') as f: return json.load(f)
        return None

    def _resolve_dim(self, dim_data):
        if isinstance(dim_data, int): return dim_data
        return random.randint(dim_data['min'], dim_data['max'])

    def _generate_complex(self, bp, parent_node, marker, campaign_id):
        print(f"=== GENERATING BUILDING: {bp.get('name')} ===")
        
        # Determine components. If type is structure, it is its own component.
        components = []
        if bp.get('type') == 'compound':
            components = bp['components']
        else:
            # Wrap single structure as one component
            components = [{'blueprint_id': bp['id'], 'offset': {'x': 0, 'y': 0}}]

        first_floor_id = None
        
        # Iterate components (Buildings in the compound)
        for comp in components:
            # If it's a compound wrapping a structure, we need to load the structure def
            # If we are already processing a structure def, we use it directly
            sub_bp_id = comp['blueprint_id']
            # Avoid infinite recursion if bp is the structure itself
            if sub_bp_id == bp.get('id'):
                sub_bp = bp
            else:
                sub_bp = self._load_blueprint(sub_bp_id)
            
            if not sub_bp: continue

            # Generate floors for this structure
            child_id = self._create_building_nodes(sub_bp, parent_node, marker, campaign_id, bp['name'])
            if not first_floor_id: first_floor_id = child_id

        return first_floor_id

    def _create_building_nodes(self, bp, parent_node, marker, campaign_id, complex_name):
        w = self._resolve_dim(bp['dimensions']['width'])
        h = self._resolve_dim(bp['dimensions']['height'])
        PADDING = 6
        map_w, map_h = w + PADDING*2, h + PADDING*2
        off_x, off_y = (map_w - w) // 2, (map_h - h) // 2
        
        first_node_id = None
        prev_node_id = None

        # Generate Floors

        for floor in bp['floors']:
            name = f"{complex_name} - {bp['name']} ({floor['name']})"

            '''            
            node_id = self.db.create_node(
                campaign_id, "building_interior", parent_node['id'],
                int(marker['world_x']), int(marker['world_y']), name
            )
            '''

                        
            grid = [[1 for _ in range(map_w)] for _ in range(map_h)]
            footprints = [{"x": off_x, "y": off_y, "w": w, "h": h, "color": "blue"}]

            # Prepare properties
            new_props = {
                "width": w,
                "height": h,
                "off_x": off_x,
                "off_y": off_y,
                "world_x": int(marker['world_x']),
                "world_y": int(marker['world_y']),
                "geometry": {"grid": grid, "width": map_w, "height": map_h, "footprints": footprints},
                "render_style": "blueprint",
                "source_marker_id": marker['id'],
                "overview": f"Floor: {floor['name']} of {bp['name']}"
            }
            
            # Create Local Map Node
            node_id = self.db.create_node(
                type="building_interior",
                name=name,
                #parent_id=parent_node['id'],
                parent_id=marker['id'], 
                properties=new_props
            )
            
            if not first_node_id: first_node_id = node_id

            # Simple linkage for single structure verticality (Up/Down)
            #if prev_node_id:
                # Add stairs in center
                #cx, cy = map_w//2, map_h//2
                #self.db.add_marker(prev_node_id, cx, cy, "stairs_down", "Stairs Down", "", properties={"portal_to": node_id})
                #self.db.add_marker(node_id, cx, cy, "stairs_up", "Stairs Up", "", properties={"portal_to": prev_node_id})
            #else:
                 # Ground floor exit to World
                 #self.db.add_marker(node_id, 2, 2, "door_out", "Exit", "", properties={"portal_to": parent_node['id']})

            prev_node_id = node_id

        return first_node_id

def get_available_blueprints():
    #print(f"**** get_available_blueprints   DATA_DIR={DATA_DIR}")
    options = []
    base = DATA_DIR / "blueprints"

    #print(f"**** get_available_blueprints   base={base}")
    for cat in ["complexes", "definitions"]:
        p = base / "structures" / cat
        if p.exists():
            for f in os.listdir(p):
                if f.endswith(".json"):
                    try:
                        with open(p / f, 'r') as fp:
                            data = json.load(fp)
                            options.append({"id": data.get("id", f), "name": data.get("name", f), "context": "Structure", "category": "Complex" if cat == "complexes" else "Definition"})
                    except: continue
    for cat in ["complexes", "definitions"]:
        p = base / "dungeons" / cat
        if p.exists():
            for f in os.listdir(p):
                if f.endswith(".json"):
                    try:
                        with open(p / f, 'r') as fp:
                            data = json.load(fp)
                            options.append({"id": data.get("id", f), "name": data.get("name", f), "context": "Dungeon", "category": "Complex" if cat == "complexes" else "Definition"})
                    except: continue
    return options
