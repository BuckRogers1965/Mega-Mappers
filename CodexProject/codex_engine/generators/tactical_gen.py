from .building_gen import BuildingGenerator
from .dungeon_gen import DungeonGenerator

class TacticalGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.building_gen = BuildingGenerator(db_manager)
        self.dungeon_gen = DungeonGenerator(db_manager)

    def generate_tactical_map(self, parent_node, marker, campaign_id):
        """
        Dispatches generation to the correct module based on marker metadata.
        """
        bp_id = marker.get('blueprint_id')
        
        # 1. Blueprint Logic
        if bp_id:
            # We need to guess if it's a building or dungeon based on some logic,
            # OR we rely on the marker symbol/metadata.
            # Ideally, the blueprint system itself would know, but here we dispatch.
            
            # Simple heuristic: If it comes from the 'dungeons' folder (we can't verify easily here without loading),
            # but usually the dropdown UI separated them.
            # Let's assume the UI set a 'type' or we check the symbol.
            
            if "skull" in marker['symbol'] or "dungeon" in marker['title'].lower():
                 print(f"--- Dispatching {marker['title']} to DungeonGenerator (Blueprint: {bp_id}) ---")
                 return self.dungeon_gen.generate_dungeon_complex(parent_node, marker, campaign_id)
            else:
                 print(f"--- Dispatching {marker['title']} to BuildingGenerator (Blueprint: {bp_id}) ---")
                 return self.building_gen.generate(parent_node, marker, campaign_id)
        
        # 2. Procedural Fallback (No Blueprint)
        elif "skull" in marker['symbol'] or "dungeon" in marker['title'].lower():
            print(f"--- Dispatching {marker['title']} to DungeonGenerator (Procedural) ---")
            return self.dungeon_gen.generate_dungeon_complex(parent_node, marker, campaign_id) # Will use default

        else:
            print("--- Unknown type, defaulting to simple generic room ---")
            return self.dungeon_gen.generate_dungeon_complex(parent_node, marker, campaign_id) # Defaults
