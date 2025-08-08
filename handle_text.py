from utils import has_value, is_truthy, find_or_create_var


def is_text_node(n: dict):
    return n["type"] == "TEXT"


def extract_node_text(node: dict):
    if has_value("characters", node, is_truthy):
        return node["characters"]
    return None


def has_text_style(n: dict) -> bool:
    return has_value("style", n) and isinstance(n["style"], dict) and len(n["style"]) > 0


def extract_text_style(n: dict):
    if not has_text_style(n):
        return None

    style = n["style"]
    text_style = {
        "fontFamily": style["fontFamily"],
        "fontWeight": style["fontWeight"],
        "fontSize": style["fontSize"],
        "lineHeight": str(style["lineHeightPx"] / style["fontSize"]) + "em" if "lineHeightPx" in style and style["lineHeightPx"] and style["fontSize"] else None,
        "letterSpacing": str((style["letterSpacing"] / style["fontSize"]) * 100) + "%" if style["letterSpacing"] and style["letterSpacing"] != 0 and style["fontSize"] else None,
        "textCase": style["textCase"],
        "textAlignHorizontal": style["textAlignHorizontal"],
        "textAlignVertical": style["textAlignVertical"],
    }

    return text_style


def extract_text(node: dict, result: dict, context: dict):
    if is_text_node(node):
        result["text"] = extract_node_text(node)

    if has_text_style(node):
        text_style = extract_text_style(node)
        result["textStyle"] = find_or_create_var(context["globalVars"], text_style, "style")
