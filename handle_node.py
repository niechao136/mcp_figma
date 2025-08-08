from handle_layout import extract_layout
from handle_text import extract_text
from handle_visual import extract_visual
from handle_comp import extract_comp
from utils import has_value


def should_children(node: dict, context: dict, option: dict):
    if option["maxDepth"] is not None and context["currentDepth"] >= option["maxDepth"]:
        return False
    return True


def extract_node(node: dict, context: dict, option: dict):
    result = {
        "id": node["id"],
        "name": node["name"],
        "type": "IMAGE-SVG" if node["type"] == "VECTOR" else node["type"],
    }
    extract_layout(node=node, result=result, context=context)
    extract_text(node=node, result=result, context=context)
    extract_visual(node=node, result=result, context=context)
    extract_comp(node=node, result=result)

    if should_children(node=node, context=context, option=option):
        children_context = {
            **context,
            "currentDepth": context["currentDepth"] + 1,
            "parent": node,
        }
        if has_value("children", node) and isinstance(node["children"], list) and len(node["children"]) > 0:
            children = [extract_node(node=child, context=children_context, option=option) for child in node["children"] if child.get("visible", True)]
            children = [child for child in children if child is not None]
            if len(children) > 0:
                result["children"] = children

    return result

