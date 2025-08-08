from utils import has_value


def extract_comp(node: dict, result: dict):
    if node["type"] == "INSTANCE":
        if has_value("componentId", node):
            result["componentId"] = node["componentId"]

        if has_value("componentProperties", node):
            component_properties = node["componentProperties"] or {}
            result["componentProperties"] = [
                {
                    "name": name,
                    "value": str(prop.get("value")),
                    "type": prop.get("type"),
                }
                for name, prop in component_properties.items()
            ]

