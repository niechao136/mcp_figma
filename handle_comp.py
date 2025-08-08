from utils import has_value


def extract_comp(node: dict, result: dict):
    if node.get("type") == "INSTANCE":
        if has_value("componentId", node):
            result["componentId"] = node.get("componentId", None)

        if has_value("componentProperties", node):
            component_properties = node.get("componentProperties", {})
            result["componentProperties"] = [
                {
                    "name": name,
                    "value": str(prop.get("value", "")),
                    "type": prop.get("type", ""),
                }
                for name, prop in component_properties.items()
            ]
