from utils import (has_value, parse_paint, find_or_create_var, is_stroke_weights, generate_css_shorthand,
                   format_rgba_color, is_rectangle_corner_radii)


def build_stroke(n: dict, has_children=False):
    strokes: dict = {
        "colors": []
    }

    if has_value("strokes", n) and isinstance(n.get("strokes", []), list) and len(n["strokes"]) > 0:
        strokes["colors"] = [parse_paint(stroke, has_children) for stroke in n.get("strokes", []) if stroke.get("visible", True)]

    if has_value("strokeWeight", n) and isinstance(n.get("strokeWeight", 0), (int, float)) and n.get("strokeWeight", 0) > 0:
        strokes["strokeWeight"] = str(n.get("strokeWeight", 0)) + "px"

    if has_value("strokeDashes", n) and isinstance(n.get("strokeDashes", []), list) and len(n.get("strokeDashes", [])) > 0:
        strokes["strokeDashes"] = n.get("strokeDashes", [])

    if has_value("individualStrokeWeights", n, is_stroke_weights):
        strokes["strokeWeight"] = generate_css_shorthand(n.get("individualStrokeWeights", {}))

    return strokes


def simply_drop_shadow(effect: dict):
    x = effect.get("offset", {}).get("x", 0)
    y = effect.get("offset", {}).get("y", 0)
    radius = effect.get("radius", 0)
    spread = effect.get("spread", 0)
    color = format_rgba_color(effect.get("color", {}))
    return f"{x}px {y}px {radius}px {spread}px {color}"


def simply_inner_shadow(effect: dict):
    x = effect.get("offset", {}).get("x", 0)
    y = effect.get("offset", {}).get("y", 0)
    radius = effect.get("radius", 0)
    spread = effect.get("spread", 0)
    color = format_rgba_color(effect.get("color", {}))
    return f"inset {x}px {y}px {radius}px {spread}px {color}"


def simply_blur(effect: dict):
    radius = effect.get("radius", 0)
    return f"blur({radius}px)"


def build_effect(n):
    if not has_value("effects", n):
        return {}

    effects = [e for e in n.get("effects", []) if e.get("visible", True)]

    drop_shadow = [simply_drop_shadow(e) for e in effects if e.get("type") == "DROP_SHADOW"]
    inner_shadow = [simply_inner_shadow(e) for e in effects if e.get("type") == "INNER_SHADOW"]
    box_shadow = ", ".join(drop_shadow + inner_shadow)

    layer = " ".join([simply_blur(e) for e in effects if e.get("type") == "LAYER_BLUR"])
    background = " ".join([simply_blur(e) for e in effects if e.get("type") == "BACKGROUND_BLUR"])

    result = {}
    if box_shadow:
        if n.get("type") == "TEXT":
            result["textShadow"] = box_shadow
        else:
            result["boxShadow"] = box_shadow
    if layer:
        result["filter"] = layer
    if background:
        result["backdropFilter"] = background

    return result


def extract_visual(node: dict, result: dict, context: dict):
    has_children = has_value("children", node) and isinstance(node.get("children", []), list) and len(node.get("children", [])) > 0

    if has_value("fills", node) and isinstance(node.get("fills", []), list) and len(node.get("fills", [])) > 0:
        fills = [parse_paint(fill, has_children) for fill in node.get("fills", [])]
        result["fills"] = find_or_create_var(context.get("globalVars", {}), fills, "fill")

    strokes = build_stroke(node, has_children)
    if len(strokes.get("colors", [])) > 0:
        result["strokes"] = find_or_create_var(context.get("globalVars", {}), strokes, "stroke")

    effects = build_effect(node)
    if len(effects) > 0:
        result["effects"] = find_or_create_var(context.get("globalVars", {}), effects, "effect")

    if has_value("opacity", node) and isinstance(node.get("opacity", 1), (int, float)) and node.get("opacity", 1) != 1:
        result["opacity"] = node.get("opacity", 1)

    if has_value("cornerRadius", node) and isinstance(node.get("cornerRadius", 0), (int, float)):
        radius = node.get("cornerRadius", 0)
        result["borderRadius"] = f"{radius}px"

    if has_value("rectangleCornerRadii", node, is_rectangle_corner_radii):
        top = node.get("rectangleCornerRadii", [0])[0]
        right = node.get("rectangleCornerRadii", [0])[1]
        bottom = node.get("rectangleCornerRadii", [0])[2]
        left = node.get("rectangleCornerRadii", [0])[3]
        result["borderRadius"] = f"{top}px {right}px {bottom}px {left}px"
