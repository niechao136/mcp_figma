from handle_layout import extract_layout
from handle_text import extract_text
from handle_visual import extract_visual
from handle_comp import extract_comp
from utils import has_value


def should_children(node: dict, context: dict, option: dict):
    if option.get("maxDepth") is not None and context.get("currentDepth", 0) >= option.get("maxDepth", 0):
        return False
    return True


def extract_node(node: dict, context: dict, option: dict):
    result: dict = {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "type": "IMAGE-SVG" if node.get("type") == "VECTOR" else node.get("type", ""),
    }

    extract_layout(node=node, result=result, context=context)
    extract_text(node=node, result=result, context=context)
    extract_visual(node=node, result=result, context=context)
    extract_comp(node=node, result=result)

    if should_children(node=node, context=context, option=option):
        children_context = {
            **context,
            "currentDepth": context.get("currentDepth", 0) + 1,
            "parent": node,
        }

        if has_value("children", node) and isinstance(node.get("children", []), list) and len(
                node.get("children", [])) > 0:
            children = [extract_node(node=child, context=children_context, option=option) for child in
                        node.get("children", []) if child.get("visible", True)]
            children = [child for child in children if child is not None]
            if len(children) > 0:
                result["children"] = children

    return result
