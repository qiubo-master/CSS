# 轮胎智能客服本地 Demo

这是一个单机可运行的 LangGraph Demo，包含：

- FastAPI 会话服务和本地聊天页面
- LangGraph 风险、路由、Mock 查询、RAG、生成和校验节点
- Mock 客户、车辆、商品、价格、订单、活动和 ES `_search` 接口
- Ollama 可用时调用 `qwen3:1.7b-q4_K_M`；不可用时自动使用确定性 Mock LLM
- Windows 原生轻量知识检索后端；接口预留 Milvus 替换边界

## 快速运行

```powershell
cd C:\Users\41150\Documents\智能客服\local-demo
.\start-all.cmd
```

浏览器访问：http://127.0.0.1:8000

停止服务：

```powershell
.\stop-all.cmd
```

## Ollama

另开终端：

```powershell
cd C:\Users\41150\Documents\智能客服\local-demo
.\start-ollama.ps1
```

模型文件统一放在工作区 `tools/models`。如果 Ollama 未启动，Demo 会自动使用 Mock LLM，页面和全流程仍可运行。

首次安装模型：

```powershell
.\install-ollama-models.ps1
```

模型安装后生成本地知识向量：

```powershell
.\.venv\Scripts\python.exe scripts\ingest_embeddings.py
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\benchmark.py
```

## 主要接口

- `GET /api/v1/health`
- `POST /api/v1/conversations`
- `POST /api/v1/conversations/{id}/messages`
- `POST /api/v1/conversations/{id}/messages/stream`（SSE 流式输出）
- `GET /mock/customers/{id}`
- `POST /mock/search/products`
- `POST /mock/orders/query`
- `POST /mock-es/{index}/_search`

流式事件依次为 `message.accepted`、`tool.status`、`answer.delta`、`citation`、`answer.completed`；异常时返回 `answer.error`。一键启动默认使用 `C:\AI` 中的真实 Ollama 模型。
