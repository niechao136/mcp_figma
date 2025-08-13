from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal, Any, Union
import httpx
import os
import asyncio
from handle_node import extract_node
from handle_image import filter_valid_images, build_svg_query_params, download_and_process_image


class FigmaClient:
    def __init__(self, token: str):
        self.base = "https://api.figma.com/v1"
        self.head = {
            "X-Figma-Token": token
        }

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base}/me", headers=self.head)
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_node(self, file_key: str, node_id: str, depth: Optional[int] = None) -> dict:
        query = f"&depth={depth}" if depth else ""
        endpoint = f"{self.base}/files/{file_key}/nodes?ids={node_id}{query}"
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(endpoint, headers=self.head)
            response.raise_for_status()
            return response.json()

    async def get_file(self, file_key: str, depth: Optional[int] = None) -> dict:
        query = f"&depth={depth}" if depth else ""
        endpoint = f"{self.base}/files/{file_key}{query}"
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(endpoint, headers=self.head)
            response.raise_for_status()
            return response.json()

    async def get_image(self, file_key: str):
        endpoint = f"{self.base}/files/{file_key}/images"
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(endpoint, headers=self.head)
            response.raise_for_status()
            res = response.json()
            return res.get("meta", {}).get("images", {})

    async def get_node_render_urls(self, file_key: str, node_ids: list[str],  img_format: Literal["png", "svg"], options: Optional[Dict[str, Any]] = None):
        if not node_ids:
            return {}

        if options is None:
            options = {}
        if img_format == "png":
            scale = options.get("pngScale", 2)
            endpoint = f"{self.base}/images/{file_key}?ids={','.join(node_ids)}&format=png&scale={scale}"
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(endpoint, headers=self.head)
                response.raise_for_status()
                return filter_valid_images(response.json().get("images", {}))
        else:
            svg_options = options.get("svgOptions", {
                "outlineText": True,
                "includeId": False,
                "simplifyStroke": True
            })
            params = build_svg_query_params(svg_ids=node_ids, svg_options=svg_options)
            endpoint = f"{self.base}/images/{file_key}?{params}"
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(endpoint, headers=self.head)
                response.raise_for_status()
                return filter_valid_images(response.json().get("images", {}))

    async def download_images(self, file_key: str, local_path: str, items: List[Dict[str, Any]], options: Dict[str, Any] = None):
        if not items:
            return []

        png_scale = options.get("pngScale", 2) if options else 2
        svg_options = options.get("svgOptions") if options else None
        download_tasks = []
        # 按类型分组
        image_fills = [item for item in items if item.get("imageRef")]
        render_nodes = [item for item in items if item.get("nodeId")]
        # 下载 image fills
        if image_fills:
            fill_urls = await self.get_image(file_key)
            fill_downloads = [
                download_and_process_image(
                    item["fileName"],
                    local_path,
                    fill_urls.get(item["imageRef"]),
                    item.get("needsCropping", False),
                    item.get("cropTransform"),
                    item.get("requiresImageDimensions", False),
                )
                for item in image_fills if fill_urls.get(item["imageRef"])
            ]
            if fill_downloads:
                download_tasks.append(asyncio.gather(*fill_downloads))
        # 下载 render nodes
        if render_nodes:
            png_nodes = [n for n in render_nodes if not n["fileName"].lower().endswith(".svg")]
            svg_nodes = [n for n in render_nodes if n["fileName"].lower().endswith(".svg")]

            # PNG 渲染
            if png_nodes:
                png_urls = await self.get_node_render_urls(
                    file_key,
                    [n["nodeId"] for n in png_nodes],
                    "png",
                    {"pngScale": png_scale},
                )
                png_downloads = [
                    download_and_process_image(
                        n["fileName"],
                        local_path,
                        png_urls.get(n["nodeId"]),
                        n.get("needsCropping", False),
                        n.get("cropTransform"),
                        n.get("requiresImageDimensions", False),
                    )
                    for n in png_nodes if png_urls.get(n["nodeId"])
                ]
                if png_downloads:
                    download_tasks.append(asyncio.gather(*png_downloads))

            # SVG 渲染
            if svg_nodes:
                svg_urls = await self.get_node_render_urls(
                    file_key,
                    [n["nodeId"] for n in svg_nodes],
                    "svg",
                    {"svgOptions": svg_options},
                )
                svg_downloads = [
                    download_and_process_image(
                        n["fileName"],
                        local_path,
                        svg_urls.get(n["nodeId"]),
                        n.get("needsCropping", False),
                        n.get("cropTransform"),
                        n.get("requiresImageDimensions", False),
                    )
                    for n in svg_nodes if svg_urls.get(n["nodeId"])
                ]
                if svg_downloads:
                    download_tasks.append(asyncio.gather(*svg_downloads))

        results_nested = await asyncio.gather(*download_tasks)
        return [item for sublist in results_nested for item in sublist]


async def get_figma(request: Request) -> FigmaClient:
    query_params = request.query_params if request else {}

    figma_token = query_params.get("figma_token")
    if not figma_token:
        raise ValueError("缺少参数 figma_token")

    client = FigmaClient(token=figma_token)

    if not await client.validate():
        raise ValueError("figma_token 无效")

    return client


class FigmaMCP(FastMCP):
    async def list_tools(self):
        request: Request = self.session_manager.app.request_context.request
        await get_figma(request=request)

        return await super().list_tools()


# Init
mcp = FigmaMCP("figma", stateless_http=True, host="0.0.0.0", port=10081)


def parse_node(result: dict, option: dict):
    component = {}
    component_set = {}
    parse = []

    if "nodes" in result:
        nodes = list(result.get("nodes", {}).values())
        for node in nodes:
            if "components" in node:
                component.update(node.get("components", {}))
            if "componentSets" in node:
                component_set.update(node.get("componentSets", {}))

        parse = [n.get("document", {}) for n in nodes if not n.get("document", {}).get("visible") is False]
    else:
        if "components" in result:
            component.update(result.get("components", {}))
        if "componentSets" in result:
            component_set.update(result.get("componentSets", {}))
        if "document" in result and "children" in result.get("document", {}).get("children", []):
            parse = [n for n in result.get("document", {}).get("children", []) if not n.get("visible", True) is False]

    simplify_component = {
        comp_id: {
            "id": comp_id,
            "key": comp.get("key", ""),
            "name": comp.get("name", ""),
            "componentSetId": comp.get("componentSetId", ""),
        } for comp_id, comp in component.items()
    }
    simplify_component_set = {
        comp_id: {
            "id": comp_id,
            "key": comp.get("key", ""),
            "name": comp.get("name", ""),
            "description": comp.get("description", ""),
        } for comp_id, comp in component.items()
    }

    context = {
        "globalVars": {
            "styles": {}
        },
        "currentDepth": 0,
    }

    extract_nodes = [extract_node(node=node, context=context, option=option) for node in parse if node.get("visible", True)]
    extract_nodes = [node for node in extract_nodes if node is not None]

    return {
        "metadata": {
            "name": result.get("name", ""),
            "lastModified": result.get("lastModified", ""),
            "thumbnailUrl": result.get("thumbnailUrl", ""),
            "components": simplify_component,
            "componentSets": simplify_component_set,
        },
        "nodes": extract_nodes,
        "globalVars": context["globalVars"],
    }



@mcp.tool()
async def get_figma_data(file_key: str, node_id: str, depth: Optional[int] = None) -> dict:
    """获取全面的 Figma 文件数据，包括布局、内容、视觉效果和组件信息

    :arg:
        file_key: 要获取的 Figma 文件的键，通常位于提供的 URL 中，例如 figma.com/(file|design)/<file_key>/...
        node_id: 要获取的节点 ID，通常位于 URL 参数 node-id=<node_id> 中，如果提供则始终使用
        depth: 控制遍历节点树的层级深度；可选，默认为 None，除非用户明确指定
    :return:
        包含 Figma 文件数据的 JSON 字符串
    """
    request: Request = mcp.session_manager.app.request_context.request
    client = await get_figma(request=request)
    if node_id:
        res = await client.get_node(file_key=file_key, node_id=node_id, depth=depth)
    else:
        res = await client.get_file(file_key=file_key, depth=depth)

    design = parse_node(result=res, option={ "maxDepth": depth })

    return design


class NodeParams(BaseModel):
    nodeId: Optional[str] = Field(None, description="Figma 节点 ID (1234:5678)")
    imageRef: Optional[str] = Field(None, description="Figma imageRef（用于 PNG/SVG 下载）")
    fileName: str = Field(..., description="本地保存文件名（带后缀）")
    needsCropping: Optional[bool] = Field(False, description="是否需要裁剪")
    cropTransform: Optional[List[List[float]]] = Field(None, description="裁剪矩阵")
    requiresImageDimensions: Optional[bool] = Field(False, description="是否需要尺寸信息")
    filenameSuffix: Optional[str] = Field(None, description="文件名后缀")


@mcp.tool()
async def download_image(file_key: str, nodes: List[NodeParams],  png_scale: Union[int, float, str], local_path: str):
    """
    用于下载 Figma 节点的图片资源（PNG / SVG）。
    **调用时机**：
    - 当用户提供的 Figma 链接或数据中存在 `imageRef` 字段时，应调用此工具下载对应图片
    - 即使用户未明确要求下载，只要有 `imageRef` 且可用，也应自动调用本工具

    :arg:
        file_key: 包含图片的 Figma 文件的键
        nodes: 要作为图片提取的节点
        png_scale: PNG 图片的导出比例。可选，如果未指定，则默认为 2。仅适用于 PNG 图片。
        local_path: 项目中存储图像的目录的绝对路径。如果该目录不存在，则会创建。此路径的格式应遵循您正在运行的操作系统的目录格式。路径名中也不要使用任何特殊转义字符。
    :return:
        包含图片下载结果的 JSON 字符串
    """
    try:
        download_items = []
        download_to_requests: Dict[int, List[str]] = {}
        seen_downloads: Dict[str, int] = {}
        for node in nodes:
            final_file_name = node.fileName
            if node.filenameSuffix and node.filenameSuffix not in final_file_name:
                name, ext = os.path.splitext(final_file_name)
                final_file_name = f"{name}-{node.filenameSuffix}{ext}"
            download_item = {
                "fileName": final_file_name,
                "needsCropping": node.needsCropping or False,
                "cropTransform": node.cropTransform,
                "requiresImageDimensions": node.requiresImageDimensions or False,
            }
            if node.imageRef:
                unique_key = f"{node.imageRef}-{node.filenameSuffix or 'none'}"
                if not node.filenameSuffix and unique_key in seen_downloads:
                    download_index = seen_downloads[unique_key]
                    requests = download_to_requests.get(download_index, [])
                    if final_file_name not in requests:
                        requests.append(final_file_name)
                    if download_item["requiresImageDimensions"]:
                        download_items[download_index]["requiresImageDimensions"] = True
                else:
                    download_index = len(download_items)
                    download_items.append({**download_item, "imageRef": node.imageRef})
                    download_to_requests[download_index] = [final_file_name]
                    seen_downloads[unique_key] = download_index
            else:
                download_index = len(download_items)
                download_items.append({**download_item, "nodeId": node.nodeId})
                download_to_requests[download_index] = [final_file_name]

        request: Request = mcp.session_manager.app.request_context.request
        client = await get_figma(request=request)
        # 执行下载
        all_downloads = await client.download_images(file_key, local_path, download_items, {
            "pngScale": png_scale
        })
        success_count = sum(1 for item in all_downloads if item)
        # 格式化结果
        images_list = []
        for index, result in enumerate(all_downloads):
            file_name = os.path.basename(result["filePath"])
            dimensions = f"{result['finalDimensions']['width']}x{result['finalDimensions']['height']}"
            crop_status = " (cropped)" if result.get("wasCropped") else ""

            if result.get("cssVariables"):
                dimension_info = f"{dimensions} | {result['cssVariables']}"
            else:
                dimension_info = dimensions

            requested_names = download_to_requests.get(index, [file_name])
            alias_text = ""
            if len(requested_names) > 1:
                aliases = [name for name in requested_names if name != file_name]
                alias_text = f" (also requested as: {', '.join(aliases)})" if aliases else ""

            images_list.append(f"- {file_name}: {dimension_info}{crop_status}{alias_text}")
        return f"Downloaded {success_count} images:\n" + "\n".join(images_list)
    except Exception as e:
        return f"Failed to download images: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

