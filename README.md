
# mcp_figma

根据链接提取 Figma 设计信息的 MCP Server

## 运行命令

```shell
# 进入项目目录
cd mcp_figma
# 安装依赖
pip install -r requirements.txt
# 运行程序
python main.py
```

## 发布命令

```shell
# 先停止
docker-compose down --rmi local -v
# 再启动
docker-compose up --build -d
```

## 配置方式

```json
{
  "mcpServers": {
    "figma": {
      "url": "http://[服务器IP]:10081/mcp?figma_token=[Figma Token]"
    }
  }
}
```
