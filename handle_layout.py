from typing import Optional, List, Dict, Any
from utils import (is_frame, legal_get, generate_css_shorthand, is_layout, is_in_auto_layout_flow, pixel_round,
                   is_rectangle, find_or_create_var)


def get_direction(axis: str, mode: str) -> str:
    if mode == "row":
        return "horizontal" if axis == "primary" else "vertical"
    elif mode == "column":
        return "vertical" if axis == "primary" else "horizontal"
    return "horizontal"


def convert_align(axis_align: str = None, stretch: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if stretch and stretch.get("mode") != "none":
        children: List[Dict[str, Any]] = stretch.get("children", [])
        mode: str = stretch.get("mode", "none")
        axis: str = stretch.get("axis", "primary")

        direction: str = get_direction(axis, mode)

        def should_stretch_child(c: Dict[str, Any]) -> bool:
            if c.get("layoutPositioning") == "ABSOLUTE":
                return True
            if direction == "horizontal":
                return c.get("layoutSizingHorizontal") == "FILL"
            elif direction == "vertical":
                return c.get("layoutSizingVertical") == "FILL"
            return False

        if children and all(should_stretch_child(c) for c in children):
            return "stretch"

    # 处理对齐方式
    if axis_align == "MIN":
        return None  # flex-start is default
    elif axis_align == "MAX":
        return "flex-end"
    elif axis_align == "CENTER":
        return "center"
    elif axis_align == "SPACE_BETWEEN":
        return "space-between"
    elif axis_align == "BASELINE":
        return "baseline"
    else:
        return None


def convert_self_align(align: str = None) -> Optional[str]:
    if align == "MIN":
        # MIN 即 flex-start，默认值，返回 None
        return None
    elif align == "MAX":
        return "flex-end"
    elif align == "CENTER":
        return "center"
    elif align == "STRETCH":
        return "stretch"
    else:
        return None


def convert_sizing(s: str | None) -> str | None:
    if s == "FIXED":
        return "fixed"
    if s == "FILL":
        return "fill"
    if s == "HUG":
        return "hug"
    return None


def build_frame(node: dict):
    if not is_frame(node):
        return {
            "mode": "none"
        }

    layout_mode = legal_get(node, "layoutMode", None)
    frame: dict = {
        "mode": (
            "none" if not layout_mode or layout_mode == "NONE"
            else "row" if layout_mode == "HORIZONTAL"
            else "column"
        )
    }

    overflow_scroll = []
    overflow_dir = legal_get(node, "overflowDirection", None)
    if overflow_dir and "HORIZONTAL" in overflow_dir:
        overflow_scroll.append("x")
    if overflow_dir and "VERTICAL" in overflow_dir:
        overflow_scroll.append("y")
    if overflow_scroll:
        frame["overflowScroll"] = overflow_scroll

    if frame["mode"] == "none":
        return frame

    primary_axis_align = legal_get(node, "primaryAxisAlignItems", "MIN")
    counter_axis_align = legal_get(node, "counterAxisAlignItems", "MIN")
    layout_align = legal_get(node, "layoutAlign", None)
    frame["justifyContent"] = convert_align(primary_axis_align, {
        "children": legal_get(node, "children", []),
        "axis": "primary",
        "mode": frame.get("mode")
    })
    frame["alignItems"] = convert_align(counter_axis_align, {
        "children": legal_get(node, "children", []),
        "axis": "counter",
        "mode": frame.get("mode")
    })
    frame["alignSelf"] = convert_self_align(layout_align)

    if node.get("layoutWrap") == "WRAP":
        frame["wrap"] = True
    item_spacing = legal_get(node, "itemSpacing", None)
    if item_spacing:
        frame["gap"] = f"{item_spacing}px"

    if any(node.get(key) for key in ["paddingTop", "paddingBottom", "paddingLeft", "paddingRight"]):
        frame["padding"] = generate_css_shorthand({
            "top": node.get("paddingTop", 0),
            "right": node.get("paddingRight", 0),
            "bottom": node.get("paddingBottom", 0),
            "left": node.get("paddingLeft", 0),
        })

    return frame


def build_layout(n: dict, mode: str, parent: Optional[dict] = None):
    if not is_layout(n):
        return None

    layout: dict = {
        "mode": mode,
        "sizing": {
            "horizontal": convert_sizing(n.get("layoutSizingHorizontal", None)),
            "vertical": convert_sizing(n.get("layoutSizingVertical", None)),
        }
    }

    if is_frame(parent) and not is_in_auto_layout_flow(n, parent):
        if n.get("layoutPositioning", None) == "ABSOLUTE":
            layout["position"] = "absolute"
        if n.get("absoluteBoundingBox", None) and parent.get("absoluteBoundingBox", None):
            layout["locationRelativeToParent"] = {
                "x": pixel_round(n.get("absoluteBoundingBox", {}).get("x", 0) - parent.get("absoluteBoundingBox", {}).get("x", 0)),
                "y": pixel_round(n.get("absoluteBoundingBox", {}).get("y", 0) - parent.get("absoluteBoundingBox", {}).get("y", 0)),
            }

    if is_rectangle("absoluteBoundingBox", n):
        dimensions = {}
        bbox = n.get("absoluteBoundingBox", {})
        width = bbox.get("width", 0)
        height = bbox.get("height", 0)

        if mode == "row":
            if not n.get("layoutGrow") and n.get("layoutSizingHorizontal") == "FIXED":
                dimensions["width"] = width
            if n.get("layoutAlign") != "STRETCH" and n.get("layoutSizingVertical") == "FIXED":
                dimensions["height"] = height

        elif mode == "column":
            if n.get("layoutAlign") != "STRETCH" and n.get("layoutSizingHorizontal") == "FIXED":
                dimensions["width"] = width
            if not n.get("layoutGrow") and n.get("layoutSizingVertical") == "FIXED":
                dimensions["height"] = height

            if n.get("preserveRatio") and width and height:
                dimensions["aspectRatio"] = width / height

        else:
            if n.get("layoutSizingHorizontal") in (None, "FIXED"):
                dimensions["width"] = width
            if n.get("layoutSizingVertical") in (None, "FIXED"):
                dimensions["height"] = height

        # Round numbers and assign if any dimensions exist
        if dimensions:
            if "width" in dimensions and dimensions["width"] is not None:
                dimensions["width"] = pixel_round(dimensions["width"])
            if "height" in dimensions and dimensions["height"] is not None:
                dimensions["height"] = pixel_round(dimensions["height"])
            layout["dimensions"] = dimensions

    return layout


def simply_layout(node: dict, parent: Optional[dict] = None):
    frame = build_frame(node=node)
    layout = build_layout(n=node, parent=parent, mode=frame.get("mode", "none")) or {}
    return {
        **frame,
        **layout,
    }


def extract_layout(node: dict, result: dict, context: dict):
    layout = simply_layout(node=node, parent=context.get("parent", None))
    if len(layout) > 1:
        result["layout"] = find_or_create_var(context.get("globalVars", {}), layout, "layout")
