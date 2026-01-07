from .db_manager import DBManager
import json

class SQLTreeAdapter:
    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    def _format_uid(self, node_id): return str(node_id)
    def _parse_uid(self, uid): return int(uid)

    def get_roots(self):
        """The entry point for the web UI shows the top-level System and Campaign nodes."""
        root = self.db.find_node('app_root')
        if not root: return []
        
        top_nodes = self.db.get_children(root['id'])
        return [{
            "uid": self._format_uid(n['id']), 
            "type": n['type'], 
            "name": n['name'], 
            "icon": "⚙️" if n['type'] == 'settings' else "📚"
        } for n in top_nodes]

    def get_node(self, uid: str):
        node_id = self._parse_uid(uid)
        node = self.db.get_node(node_id)
        if not node: return None

        # 1. Flatten Data: debug IDs + Name + everything in Properties
        flat_data = {
            "node_id": node['id'], 
            "parent_id": node['parent_id'],
            "name": node['name']
        }
        props = node.get('properties', {})
        flat_data.update(props)
        
        # 2. BUILD DYNAMIC UI SCHEMA
        # Prepend the debug IDs as readonly fields
        ui_schema = [
            {"key": "node_id", "label": "Node ID", "type": "text", "readonly": True},
            {"key": "parent_id", "label": "Parent ID", "type": "text", "readonly": True},
            {"key": "name", "label": "Name", "type": "text"}
        ]
        
        for key, value in props.items():
            # Basic type detection for the web form
            field_type = "text"
            if isinstance(value, (int, float)):
                field_type = "text" # HTML input type number can be finicky with floats, text is safer for now
            elif isinstance(value, str) and (len(value) > 60 or "\n" in value):
                field_type = "textarea"
            elif isinstance(value, (dict, list)):
                # If it's complex data (like geometry or metadata), show it as a read-only JSON string
                field_type = "textarea" 
                flat_data[key] = json.dumps(value, indent=2)

            ui_schema.append({
                "key": key,
                "label": key.replace('_', ' ').title(),
                "type": field_type
            })

        # 3. Determine Navigation Children
        children_nodes = self.db.get_children(node_id)
        children_summaries = []
        icons = {
            'poi': '📍', 'npc': '👤', 'local_map': '🗺️', 
            'dungeon_level': '💀', 'server_config': '🖥️',
            'ai_provider': '🧠', 'display_config': '📺'
        }
        
        for c in children_nodes:
            children_summaries.append({
                "uid": self._format_uid(c['id']),
                "type": c['type'],
                "name": c['name'],
                "icon": icons.get(c['type'], '📄')
            })

        return {
            "uid": uid,
            "parent_uid": self._format_uid(node['parent_id']) if node['parent_id'] else None,
            "type": node['type'],
            "name": node['name'],
            "data": flat_data,
            "ui_schema": ui_schema,
            "children": children_summaries
        }

    def update_node(self, uid: str, form_data: dict):
        node_id = self._parse_uid(uid)
        name = form_data.pop('name', None)
        
        # Clean up any JSON strings that should be objects before saving
        # (Allows editing complex properties if the user keeps the JSON valid)
        for k, v in form_data.items():
            if isinstance(v, str) and (v.startswith('{') or v.startswith('[')):
                try:
                    form_data[k] = json.loads(v)
                except:
                    pass # Keep as string if not valid JSON

        self.db.update_node(node_id, name=name, properties=form_data)