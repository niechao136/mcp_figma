from utils import has_value, is_truthy, find_or_create_var
from typing import Any


def is_text_node(n: dict):
    return n.get("type") == "TEXT"


def extract_node_text(node: dict) -> Any:
    if has_value("characters", node, is_truthy):
        return node.get("characters", None)
    return None


def has_text_style(n: dict) -> bool:
    return has_value("style", n) and isinstance(n.get("style"), dict) and len(n.get("style", {})) > 0


def extract_text_style(n: dict):
    if not has_text_style(n):
        return None

    style = n.get("style", {})
    text_style = {
        "fontFamily": style.get("fontFamily", ""),
        "fontWeight": style.get("fontWeight", ""),
        "fontSize": style.get("fontSize", ""),
        "lineHeight": str(style.get("lineHeightPx", 0) / style.get("fontSize", 1)) + "em" if style.get("lineHeightPx") and style.get("fontSize") else None,
        "letterSpacing": str((style.get("letterSpacing", 0) / style.get("fontSize", 1)) * 100) + "%" if style.get("letterSpacing") and style.get("letterSpacing") != 0 and style.get("fontSize") else None,
        "textCase": style.get("textCase", ""),
        "textAlignHorizontal": style.get("textAlignHorizontal", ""),
        "textAlignVertical": style.get("textAlignVertical", ""),
    }

    return text_style


def extract_text(node: dict, result: dict, context: dict):
    if is_text_node(node):
        result["text"] = extract_node_text(node)

    if has_text_style(node):
        text_style = extract_text_style(node)
        result["textStyle"] = find_or_create_var(context.get("globalVars", {}), text_style, "style")
