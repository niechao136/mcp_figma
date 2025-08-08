from utils import (has_value, parse_paint, find_or_create_var, is_stroke_weights, generate_css_shorthand,
                   format_rgba_color, is_rectangle_corner_radii)


def build_stroke(n: dict, has_children = False):
    strokes: dict = {
        "colors": []
    }

    if has_value("strokes", n) and isinstance(n["strokes"], list) and len(n["strokes"]) > 0:
        strokes["colors"] = [parse_paint(stroke, has_children) for stroke in n["strokes"] if stroke.get("visible", True)]

    if has_value("strokeWeight", n) and isinstance(n["strokeWeight"], (int, float)) and n["strokeWeight"] > 0:
        strokes["strokeWeight"] = str(n["strokeWeight"]) + "px"

    if has_value("strokeDashes", n) and isinstance(n["strokeDashes"], list) and len(n["strokeDashes"]) > 0:
        strokes["strokeDashes"] = n["strokeDashes"]

    if has_value("individualStrokeWeights", n, is_stroke_weights):
        strokes["strokeWeight"] = generate_css_shorthand(n["individualStrokeWeights"])

    return strokes


def simply_drop_shadow(effect: dict):
    x = effect["offset"]["x"]
    y = effect["offset"]["y"]
    radius = effect["radius"]
    spread = effect["spread"] or 0
    color = format_rgba_color(effect["color"])
    return f"{x}px {y}px {radius}px {spread}px {color}"


def simply_inner_shadow(effect: dict):
    x = effect["offset"]["x"]
    y = effect["offset"]["y"]
    radius = effect["radius"]
    spread = effect["spread"] or 0
    color = format_rgba_color(effect["color"])
    return f"inset {x}px {y}px {radius}px {spread}px {color}"


def simply_blur(effect: dict):
    radius = effect["radius"]
    return f"blur({radius}px)"


def build_effect(n):
    if not has_value("effects", n):
        return {}

    effects = [e for e in n["effects"] if e["visible"]]

    drop_shadow = [simply_drop_shadow(e) for e in effects if e["type"] == "DROP_SHADOW"]
    inner_shadow = [simply_inner_shadow(e) for e in effects if e["type"] == "INNER_SHADOW"]
    box_shadow = ", ".join(drop_shadow + inner_shadow)

    layer = " ".join([simply_blur(e) for e in effects if e["type"] == "LAYER_BLUR"])
    background = " ".join([simply_blur(e) for e in effects if e["type"] == "BACKGROUND_BLUR"])

    result = {}
    if box_shadow:
        if n["type"] == "TEXT":
            result["textShadow"] = box_shadow
        else:
            result["boxShadow"] = box_shadow
    if layer:
        result["filter"] = layer
    if background:
        result["backdropFilter"] = background

    return result


def extract_visual(node: dict, result: dict, context: dict):
    has_children = has_value("children", node) and isinstance(node["children"], list) and len(node["children"]) > 0

    if has_value("fills", node) and isinstance(node["fills"], list) and len(node["fills"]) > 0:
        fills = [parse_paint(fill, has_children) for fill in node["fills"]]
        result["fills"] = find_or_create_var(context["globalVars"], fills, "fill")

    strokes = build_stroke(node, has_children)
    if len(strokes["colors"]) > 0:
        result["strokes"] = find_or_create_var(context["globalVars"], strokes, "stroke")

    effects = build_effect(node)
    if len(effects) > 0:
        result["effects"] = find_or_create_var(context["globalVars"], effects, "effect")

    if has_value("opacity", node) and isinstance(node["opacity"], (int, float)) and node["opacity"] != 1:
        result["opacity"] = node["opacity"]

    if has_value("cornerRadius", node) and isinstance(node["cornerRadius"], (int, float)):
        radius = node["cornerRadius"]
        result["borderRadius"] = f"{radius}px"

    if has_value("rectangleCornerRadii", node, is_rectangle_corner_radii):
        top = node["rectangleCornerRadii"][0]
        right = node["rectangleCornerRadii"][1]
        bottom = node["rectangleCornerRadii"][2]
        left = node["rectangleCornerRadii"][3]
        result["borderRadius"] = f"{top}px {right}px {bottom}px {left}px"

