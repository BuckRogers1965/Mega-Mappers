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
            # Keep headers and separators as-is
            if line.startswith("---") or line.startswith("CAMPAIGN") or line.startswith("LOCATION") or line.startswith("MAP") or line.strip() == "":
                wrapped.append(line)
            else:
                # Wrap regular text
                wrapped.extend(textwrap.wrap(line, width=width))
        return wrapped

class WorldContent(ContentManager):
    def get_info_text(self):
        # 1. Fetch Campaign Data
        cid = self.node.get('campaign_id')
        campaign = self.db.get_campaign(cid)
        
        meta = self.node.get('metadata', {})
        
        lines = []
        if campaign:
            lines.append(f"CAMPAIGN: {campaign.get('name', 'Unknown')}")
            lines.append(f"Theme: {campaign.get('theme_id', '').title()}")
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
        meta = self.node.get('metadata', {})
        lines = []
        
        # Header
        lines.append(f"LOCATION: {self.node.get('name')}")
        lines.append("")
        
        # Overview
        overview = meta.get('overview', "No overview available.")
        lines.append("--- OVERVIEW ---")
        wrapped_overview = textwrap.wrap(overview, width=30)
        lines.extend(wrapped_overview)
        lines.append("")
        
        # Fetch Real Data from DB
        npcs = self.db.get_npcs_for_node(self.node['id'])
        
        if npcs:
            lines.append("--- INHABITANTS ---")
            for npc in npcs:
                name = npc.get('name', 'Unknown')
                role = npc.get('role', 'Unknown')
                lines.append(f"• {name}")
                lines.append(f"  ({role})")
            lines.append("")

        # Rumors (Metadata)
        rumors = meta.get('rumors', [])
        if rumors:
            lines.append("--- RUMORS & HOOKS ---")
            for r in rumors:
                # Wrap each rumor
                wrapped_rumor = textwrap.wrap("* " + r, width=30, subsequent_indent="  ")
                lines.extend(wrapped_rumor)
                lines.append("")
                
        return lines

class TacticalContent(ContentManager):
    def get_info_text(self):
        meta = self.node.get('metadata', {})
        geo = self.node.get('geometry_data', {})
        
        lines = []
        lines.append(f"SITE: {self.node.get('name')}")
        lines.append(f"Type: {self.node.get('type').replace('_', ' ').title()}")
        lines.append(f"Size: {geo.get('width')}x{geo.get('height')} Tiles")
        lines.append("")
        
        overview = meta.get('overview', "")
        if overview:
            lines.append("--- OVERVIEW ---")
            lines.extend(textwrap.wrap(overview, width=35))
            lines.append("")
            
        encounters = meta.get('encounters', [])
        if encounters:
            lines.append("--- ENCOUNTERS ---")
            for item in encounters:
                lines.append(f"• {item}")
            lines.append("")

        loot = meta.get('loot', [])
        if loot:
            lines.append("--- LOOT ---")
            for item in loot:
                lines.append(f"• {item}")
            lines.append("")
            
        return lines

class TacticalContent_old(ContentManager):
    def get_info_text(self):
        meta = self.node.get('metadata', {})
        geo = self.node.get('geometry_data', {})
        
        lines = []
        lines.append(f"SITE: {self.node.get('name')}")
        lines.append(f"Type: {self.node.get('type').replace('_', ' ').title()}")
        lines.append(f"Size: {geo.get('width')}x{geo.get('height')} Tiles")
        lines.append("")
        
        overview = meta.get('overview', "")
        if overview:
            lines.append("--- DESCRIPTION ---")
            lines.extend(textwrap.wrap(overview, width=35))
            lines.append("")
            
        # Count Entities
        markers = self.db.get_markers(self.node['id'])
        if markers:
            lines.append(f"Objects/Markers: {len(markers)}")
            
        return lines
