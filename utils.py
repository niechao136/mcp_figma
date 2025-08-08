from typing import Optional, Dict, Any, Callable, Tuple, List
import json
import random
import string


def generate_css_shorthand(values: dict, ignore_zero: bool = True, suffix: str = "px") -> Optional[str]:
    top = values["top"]
    right = values["right"]
    bottom = values["bottom"]
    left = values["left"]

    if ignore_zero and top == 0 and right == 0 and bottom == 0 and left == 0:
        return None

    if top == right == bottom == left:
        return f"{top}{suffix}"

    if right == left:
        if top == bottom:
            return f"{top}{suffix} {right}{suffix}"
        return f"{top}{suffix} {right}{suffix} {bottom}{suffix}"

    return f"{top}{suffix} {right}{suffix} {bottom}{suffix} {left}{suffix}"


def legal_get(obj, key: str, default = None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    else:
        return getattr(obj, key, default)


def is_frame(val) -> bool:
    if isinstance(val, dict):
        return "clipsContent" in val and isinstance(val["clipsContent"], bool)
    else:
        return hasattr(val, "clipsContent") and isinstance(getattr(val, "clipsContent"), bool)


def is_layout(val) -> bool:
    if isinstance(val, dict):
        box = val.get("absoluteBoundingBox")
    else:
        box = getattr(val, "absoluteBoundingBox", None)

    return (
        isinstance(box, dict) and
        all(k in box for k in ("x", "y", "width", "height"))
    )


def is_in_auto_layout_flow(node: dict, parent: dict) -> bool:
    auto_layout_modes = ["HORIZONTAL", "VERTICAL"]
    return (
        is_frame(parent)
        and parent.get("layoutMode", "NONE") in auto_layout_modes
        and is_layout(node)
        and node.get("layoutPositioning") != "ABSOLUTE"
    )


def pixel_round(num: float) -> float:
    if not isinstance(num, (int, float)) or num != num:  # 检查 NaN
        raise TypeError("Input must be a valid number")
    return round(num, 2)



def is_rectangle(key: str, obj: Dict[str, Any]) -> bool:
    """
    检查 obj[key] 是否是一个包含 x, y, width, height 的 dict。
    相当于 TypeScript 的类型守卫。
    """
    if not isinstance(obj, dict):
        return False

    value = obj.get(key)
    if not isinstance(value, dict):
        return False

    required_keys = ["x", "y", "width", "height"]
    return all(k in value and isinstance(value[k], (int, float)) for k in required_keys)


def generate_var_id(prefix: str = "var") -> str:
    chars = string.ascii_uppercase + string.digits
    result = ''.join(random.choice(chars) for _ in range(6))
    return f"{prefix}_{result}"


def find_or_create_var(global_vars: Dict[str, Any], value: Any, prefix: str) -> str:
    # 查找已存在的变量名
    for var_id, existing_value in global_vars.get("styles", {}).items():
        if json.dumps(existing_value, sort_keys=True) == json.dumps(value, sort_keys=True):
            return var_id

    # 不存在则创建新变量
    var_id = generate_var_id(prefix)
    global_vars.setdefault("styles", {})[var_id] = value
    return var_id


def has_value(key: str, obj: Any, type_guard: Optional[Callable[[Any], bool]] = None) -> bool:
    """
    判断 obj 是否为非 None 的 dict，且包含 key。
    如果提供 type_guard，则使用它验证值，否则判断值是否不为 None。
    """
    if not isinstance(obj, dict):
        return False

    if key not in obj:
        return False

    val = obj[key]

    if type_guard:
        return type_guard(val)
    else:
        return val is not None


def is_truthy(val) -> bool:
    return bool(val)


def translate_scale_mode(scale_mode: str, has_children: bool, scaling_factor: Optional[float] = None) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    is_background = has_children

    if scale_mode == "FILL":
        css = {
            "backgroundSize": "cover",
            "backgroundRepeat": "no-repeat",
            "isBackground": True
        } if is_background else {
            "objectFit": "cover",
            "isBackground": False
        }
        processing = {
            "needsCropping": False,
            "requiresImageDimensions": False
        }

    elif scale_mode == "FIT":
        css = {
            "backgroundSize": "contain",
            "backgroundRepeat": "no-repeat",
            "isBackground": True
        } if is_background else {
            "objectFit": "contain",
            "isBackground": False
        }
        processing = {
            "needsCropping": False,
            "requiresImageDimensions": False
        }

    elif scale_mode == "TILE":
        background_size = (
            f"calc(var(--original-width) * {scaling_factor}) "
            f"calc(var(--original-height) * {scaling_factor})"
            if scaling_factor is not None else "auto"
        )
        css = {
            "backgroundRepeat": "repeat",
            "backgroundSize": background_size,
            "isBackground": True
        }
        processing = {
            "needsCropping": False,
            "requiresImageDimensions": True
        }

    elif scale_mode == "STRETCH":
        css = {
            "backgroundSize": "100% 100%",
            "backgroundRepeat": "no-repeat",
            "isBackground": True
        } if is_background else {
            "objectFit": "fill",
            "isBackground": False
        }
        processing = {
            "needsCropping": False,
            "requiresImageDimensions": False
        }

    else:
        css = {}
        processing = {
            "needsCropping": False,
            "requiresImageDimensions": False
        }

    return css, processing


def generate_transform_hash(transform: List[List[float]]) -> str:
    # 将二维数组拍平成一维
    values = [val for row in transform for val in row]
    hash_val = 0

    for val in values:
        str_val = str(val)
        for char in str_val:
            hash_val = ((hash_val << 5) - hash_val + ord(char)) & 0xffffffff

    # 转成正整数十六进制字符串，取前 6 位
    return hex(abs(hash_val))[2:].zfill(6)[:6]


def handle_image_transform(image_transform: List[List[float]]) -> Dict[str, Any]:
    transform_hash = generate_transform_hash(image_transform)
    return {
        "needsCropping": True,
        "requiresImageDimensions": False,
        "cropTransform": image_transform,
        "filenameSuffix": f"{transform_hash}",
    }


def convert_color(color: dict, opacity: Optional[float] = 1.0) -> Tuple[str, float]:
    r = round(color["r"] * 255)
    g = round(color["g"] * 255)
    b = round(color["b"] * 255)

    # 透明度相乘，并保留两位小数
    a = round(opacity * color["a"] * 100) / 100

    # 构造 #RRGGBB
    hex_color = "#{:02X}{:02X}{:02X}".format(r, g, b)

    return hex_color, a


def format_rgba_color(color: dict, opacity: Optional[float] = 1.0):
    r = round(color["r"] * 255)
    g = round(color["g"] * 255)
    b = round(color["b"] * 255)
    # 透明度相乘，并保留两位小数
    a = round(opacity * color["a"] * 100) / 100

    return f"rgba({r}, {g}, {b}, {a})"


def parse_pattern_paint(raw: dict):
    background_repeat = "repeat"
    horizontal = "center" if raw["horizontalAlignment"] == "CENTER" else "right" if raw["horizontalAlignment"] == "END" else "left"
    vertical = "center" if raw["verticalAlignment"] == "CENTER" else "bottom" if raw["verticalAlignment"] == "END" else "top"

    return {
        "type": raw["type"],
        "patternSource": {
            "type": "IMAGE-PNG",
            "nodeId": raw["sourceNodeId"],
        },
        "backgroundRepeat": background_repeat,
        "backgroundSize": str(round(raw["scalingFactor"] * 100)) + "%",
        "backgroundPosition": f"{horizontal} {vertical}"
    }


def parse_paint(raw: dict, has_children = False):
    if raw["type"] == "IMAGE":
        base = {
            "type": "IMAGE",
            "imageRef": raw["imageRef"],
            "scaleMode": raw["scaleMode"],
            "scalingFactor": raw["scalingFactor"],
        }

        is_background = has_children or base["scaleMode"] == "TILE"
        css, processing = translate_scale_mode(base["scaleMode"], is_background, raw["scalingFactor"])

        final_processing = processing
        if raw["imageTransform"]:
            transform_processing = handle_image_transform(raw["imageTransform"])
            final_processing = {
                **processing,
                **transform_processing,
                "requiresImageDimensions": processing["requiresImageDimensions"] or transform_processing["requiresImageDimensions"]
            }

        return {
            **base,
            **css,
            "imageDownloadArguments": final_processing,
        }
    elif raw["type"] == "SOLID":
        color, opacity = convert_color(raw["color"], raw["opacity"])
        return color if opacity == 1 else format_rgba_color(raw["color"], raw["opacity"])
    elif raw["type"] == "PATTERN":
        return parse_pattern_paint(raw)
    elif raw["type"] in ["GRADIENT_LINEAR", "GRADIENT_RADIAL", "GRADIENT_ANGULAR", "GRADIENT_DIAMOND"]:
        return {
            "type": raw["type"],
            "gradientHandlePositions": raw["gradientHandlePositions"],
            "gradientStops": [
                {
                    "position": stop["position"],
                    "color": convert_color(stop["color"])
                }
                for stop in raw["gradientStops"]
            ]
        }
    else:
        raise ValueError("Unknown paint type: " + raw["type"])


def is_stroke_weights(val: object) -> bool:
    if not isinstance(val, dict):
        return False
    return all(k in val for k in ("top", "right", "bottom", "left"))


def is_rectangle_corner_radii(val: Any) -> bool:
    return (
        isinstance(val, list) and
        len(val) == 4 and
        all(isinstance(v, (int, float)) for v in val)
    )

