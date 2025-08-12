import os
import aiohttp
from pathlib import Path
from PIL import Image
from typing import Dict, Optional, Any, List
from urllib.parse import urlencode


def filter_valid_images(images: Optional[Dict[str, Optional[str]]]) -> Dict[str, str]:
    if not images:
        return {}
    # 过滤掉值为 None 或空字符串的项
    return {key: value for key, value in images.items() if value}


def build_svg_query_params(svg_ids: List[str], svg_options: Dict[str, bool]) -> str:
    params = {
        "ids": ",".join(svg_ids),
        "format": "svg",
        "svg_outline_text": str(svg_options.get("outlineText", False)).lower(),
        "svg_include_id": str(svg_options.get("includeId", False)).lower(),
        "svg_simplify_stroke": str(svg_options.get("simplifyStroke", False)).lower(),
    }
    return urlencode(params)


async def download_figma_image(file_name: str, local_path: str, image_url: str) -> str:
    # 确保目录存在
    Path(local_path).mkdir(parents=True, exist_ok=True)
    full_path = Path(local_path) / file_name

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download image: {response.status} {response.reason}")

                # 以二进制写入流方式保存
                with open(full_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(1024):
                        f.write(chunk)

        return str(full_path)

    except Exception as e:
        if full_path.exists():
            os.remove(full_path)  # 删除半成品文件
        raise Exception(f"Error downloading image: {e}") from e


async def get_image_dimensions(image_path: str) -> dict:
    """
    获取图片宽高，如果失败则返回默认值 1000x1000
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if not width or not height:
                raise ValueError(f"Could not get image dimensions for {image_path}")
            return {"width": width, "height": height}
    except Exception:
        # 返回默认尺寸
        return {"width": 1000, "height": 1000}


def generate_image_css_variables(param: dict) -> str:
    """
    生成图片尺寸相关的 CSS 变量字符串
    """
    width = param.get("width")
    height = param.get("height")
    return f"--original-width: {width}px; --original-height: {height}px;"


def apply_crop_transform(image_path: str, crop_transform: list) -> str:
    """
    按 Figma transform 矩阵裁剪图片，覆盖原文件
    crop_transform 格式: [[scaleX, skewX, translateX], [skewY, scaleY, translateY]]
    """
    try:
        # 提取 transform 参数
        scale_x = crop_transform[0][0] if crop_transform[0][0] is not None else 1
        translate_x = crop_transform[0][2] if crop_transform[0][2] is not None else 0
        scale_y = crop_transform[1][1] if crop_transform[1][1] is not None else 1
        translate_y = crop_transform[1][2] if crop_transform[1][2] is not None else 0

        # 打开图片获取尺寸
        with Image.open(image_path) as img:
            width, height = img.size

            if not width or not height:
                raise ValueError(f"Could not get image dimensions for {image_path}")

            # 计算裁剪区域
            crop_left = max(0, round(translate_x * width))
            crop_top = max(0, round(translate_y * height))
            crop_width = min(width - crop_left, round(scale_x * width))
            crop_height = min(height - crop_top, round(scale_y * height))

            # 验证裁剪尺寸
            if crop_width <= 0 or crop_height <= 0:
                return image_path

            # 临时文件路径
            temp_path = image_path + ".tmp"

            # 裁剪并保存临时文件
            cropped_img = img.crop((
                crop_left,
                crop_top,
                crop_left + crop_width,
                crop_top + crop_height
            ))
            cropped_img.save(temp_path)

        # 替换原文件
        os.replace(temp_path, image_path)

        return image_path

    except Exception:
        return image_path


async def download_and_process_image(
    file_name: str,
    local_path: str,
    image_url: str,
    needs_cropping: bool = False,
    crop_transform: Optional[list] = None,
    requires_image_dimensions: bool = False
) -> Dict[str, Any]:
    processing_log = []

    # 下载原图
    original_path = await download_figma_image(file_name, local_path, image_url)

    # 获取原始尺寸
    original_dimensions = await get_image_dimensions(original_path)

    final_path = original_path
    was_cropped = False
    crop_region = None

    # 裁剪
    if needs_cropping and crop_transform:
        scale_x = crop_transform[0][0] if crop_transform[0][0] is not None else 1
        scale_y = crop_transform[1][1] if crop_transform[1][1] is not None else 1
        translate_x = crop_transform[0][2] if crop_transform[0][2] is not None else 0
        translate_y = crop_transform[1][2] if crop_transform[1][2] is not None else 0

        crop_left = max(0, round(translate_x * original_dimensions.get("width")))
        crop_top = max(0, round(translate_y * original_dimensions.get("height")))
        crop_width = min(original_dimensions.get("width") - crop_left, round(scale_x * original_dimensions.get("width")))
        crop_height = min(original_dimensions.get("height") - crop_top, round(scale_y * original_dimensions.get("height")))

        if crop_width > 0 and crop_height > 0:
            crop_region = {"left": crop_left, "top": crop_top, "width": crop_width, "height": crop_height}
            final_path = apply_crop_transform(original_path, crop_transform)
            was_cropped = True

    # 获取最终尺寸
    final_dimensions = await get_image_dimensions(final_path)

    css_variables = None
    if requires_image_dimensions:
        css_variables = generate_image_css_variables(final_dimensions)

    return {
        "filePath": final_path,
        "originalDimensions": original_dimensions,
        "finalDimensions": final_dimensions,
        "wasCropped": was_cropped,
        "cropRegion": crop_region,
        "cssVariables": css_variables,
        "processingLog": processing_log
    }

