from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from typing import Optional
import httpx
from handle_node import extract_node


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
        nodes = list(result["nodes"].values())
        for node in nodes:
            if "components" in node:
                component.update(node["components"])
            if "componentSets" in node:
                component_set.update(node["componentSets"])

        parse = [n["document"] for n in nodes if not n["document"].get("visible") is False]
    else:
        if "components" in result:
            component.update(result["components"])
        if "componentSets" in result:
            component_set.update(result["componentSets"])
        if "document" in result and "children" in result["document"]:
            parse = [n for n in result["document"]["children"] if not n.get("visible") is False]

    simplify_component = {
        comp_id: {
            "id": comp_id,
            "key": comp.get("key"),
            "name": comp.get("name"),
            "componentSetId": comp.get("componentSetId"),
        } for comp_id, comp in component.items()
    }
    simplify_component_set = {
        comp_id: {
            "id": comp_id,
            "key": comp.get("key"),
            "name": comp.get("name"),
            "description": comp.get("description"),
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
            "name": result.get("name"),
            "lastModified": result.get("lastModified"),
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
        depth: 控制遍历节点树的层级深度；可选，除非用户明确要求，否则请勿使用。
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

