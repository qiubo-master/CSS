# 本地 Demo 交付记录

## 已完成

- 便携 Python 3.11.15：`../tools/python`
- uv 0.12.3：`../tools/uv`
- Ollama 0.32.6（CPU模式）：`../tools/ollama`
- `qwen3:1.7b-q4_K_M`（1.4GB）：`../tools/models`
- `qwen3-embedding:0.6b`（639MB）：`../tools/models`
- 实际运行目录已迁移为纯英文路径：`C:\AI\ollama`、`C:\AI\models`
- FastAPI + LangGraph 项目与虚拟环境
- Mock 客户、车辆、商品、价格、订单、营销数据
- Mock ES `_search` 接口
- Qwen Embedding 生成的1024维本地知识向量及 Milvus Repository 替换边界
- 路由、检索、二次生成、答案校验、人工转接 LangGraph
- 本地客服聊天页面
- SSE 流式接口与前端增量渲染
- 自动化测试：9 passed
- 自动测试：8 passed
- Mock 模式基准：5 个场景 mean 7.79ms，P95 11.02ms
- 服务地址：http://127.0.0.1:8000

## 真实模型验收

| 场景 | 路由模型 | 检索 | 答案模型 | 总耗时 |
|---|---:|---:|---:|---:|
| 规格知识 | 9.61s | 2.60s | 19.24s | 31.46s |
| 车型价格 | 9.45s | <1ms | 20.82s | 30.28s |
| 订单预约 | 10.17s | <1ms | 9.31s | 19.50s |

本机使用CPU推理，三类真实场景均成功。与Mock模式相比，主要耗时来自两次大模型调用。价格答案经过程序化门控，强制补充地区、更新时间和最终结算声明。

## 环境差异

WSL2 系统功能需要 Windows 管理员权限；当前自动安装返回 DISM 740，因此本次使用 Windows 原生运行模式。Milvus Lite 留作 WSL2 启用后的替换项，当前可运行后端使用本地轻量检索实现，接口边界保持不变。

## 运行

```powershell
cd C:\Users\41150\Documents\智能客服\local-demo
.\start-all.cmd
```

停止：

```powershell
.\stop-all.cmd
```
