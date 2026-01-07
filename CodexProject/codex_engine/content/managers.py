import textwrap

class ContentManager:
    def __init__(self, db, node):
        self.db = db
        self.node = node

    def get_info_text(self):
        """Returns a list of strings to be displayed in the Info Panel."""
        return ["No data available."]
    
    def _wrap_lines(self, lines, width=30):
        """Helper to wrap all lines to specified width."""
        wrapped = []
        for line in lines:
            if line.startswith("---") or line.startswith("CAMPAIGN") or line.startswith("LOCATION") or line.startswith("MAP") or line.strip() == "":
                wrapped.append(line)
            else:
                wrapped.extend(textwrap.wrap(line, width=width))
        return wrapped

class WorldContent(ContentManager):
    def get_info_text(self):
        # 1. Fetch Campaign Node using generic get_node
        cid = self.node.get('parent_id') 
        campaign = self.db.get_node(cid) if cid else {}
        
        # 2. Access properties (was flattened, now strictly in properties dict)
        meta = self.node.get('properties', {})
        
        lines = []
        if campaign:
            camp_props = campaign.get('properties', {})
            lines.append(f"CAMPAIGN: {campaign.get('name', 'Unknown')}")
            lines.append(f"Theme: {camp_props.get('theme', '').title()}")
            lines.append(f"Created: {campaign.get('created_at', '')[:10]}")
            lines.append("")
            
        lines.append(f"MAP: {self.node.get('name')}")
        lines.append(f"Dimensions: {meta.get('width')}x{meta.get('height')} px")
        
        real_min = meta.get('real_min', 0)
        real_max = meta.get('real_max', 0)
        lines.append(f"Elevation: {real_min:.0f}m to {real_max:.0f}m")
        
        return self._wrap_lines(lines)

class LocalContent(ContentManager):
    def get_info_text(self):
        meta = self.node.get('properties', {})
        lines = []
        
        lines.append(f"LOCATION: {self.node.get('name')}")
        lines.append("")
        
        overview = meta.get('overview', "No overview available.")
        lines.append("--- OVERVIEW ---")
        wrapped_overview = textwrap.wrap(overview, width=30)
        lines.extend(wrapped_overview)
        lines.append("")
        
        # --- FIX: Use generic get_children instead of get_npcs_for_node ---
        npcs = self.db.get_children(self.node['id'], type_filter='npc')
        
        if npcs:
            lines.append("--- INHABITANTS ---")
            for npc in npcs:
                n_props = npc.get('properties', {})
                name = npc.get('name', 'Unknown')
                role = n_props.get('role', 'Unknown')
                lines.append(f"• {name}")
                lines.append(f"  ({role})")
            lines.append("")

        rumors = meta.get('rumors', [])
        if rumors:
            lines.append("--- RUMORS & HOOKS ---")
            for r in rumors:
                wrapped_rumor = textwrap.wrap("* " + r, width=30, subsequent_indent="  ")
                lines.extend(wrapped_rumor)
                lines.append("")
                
        return lines

class TacticalContent(ContentManager):
    def get_info_text(self):
        # --- FIX: Read from properties ---
        props = self.node.get('properties', {})
        geo = props.get('geometry_data', {})
        
        lines = []
        lines.append(f"SITE: {self.node.get('name')}")
        lines.append(f"Type: {self.node.get('type').replace('_', ' ').title()}")
        lines.append(f"Size: {geo.get('width', 0)}x{geo.get('height', 0)} Tiles")
        lines.append("")
        
        overview = props.get('overview', "")
        if overview:
            lines.append("--- OVERVIEW ---")
            lines.extend(textwrap.wrap(overview, width=35))
            lines.append("")
            
        encounters = props.get('encounters', [])
        if encounters:
            lines.append("--- ENCOUNTERS ---")
            for item in encounters:
                lines.append(f"• {item}")
            lines.append("")

        loot = props.get('loot', [])
        if loot:
            lines.append("--- LOOT ---")
            for item in loot:
                lines.append(f"• {item}")
            lines.append("")
            
        return lines
