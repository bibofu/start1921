# 流式回答与 Markdown（2026-09-07）

## 行为

聊天页面改用 `POST /api/questions/stream`。服务端向 DeepSeek 请求真实的 `stream: true` 响应，并把正文增量通过 SSE 转发给浏览器；页面边接收边渲染 Markdown，不再等完整回答后回放。未展示模型的 `reasoning_content`。原有 JSON 问答接口保持兼容，两个入口共用证据包、提示词（`grounded-answer-v8`）和最终回答构造。

| 事件 | 数据 | 前端行为 |
| --- | --- | --- |
| `status` | `{message}` | 展示检索、生成进度 |
| `delta` | `{text}` | 追加正文并立即渲染 Markdown |
| `done` | 完整 `AnswerResponse` | 补上引用和限制，保存会话上下文 |
| `error` | `{message}` | 显示可读错误；用户消息标记为失败，不生成助手消息 |

模型输出结束后直接交付，不再执行引用、页码、日期或未引用事实校验，也不再发起修复。截断、断流、超时、限流或未配置模型时仍保留原有摘录/错误兜底。正文在 `delta` 阶段实时渲染，`done` 只补齐引用/限制并结束状态。结构化或无模型路径没有可流式正文，直接发送 `done`。

生产链路不再根据 Markdown 结构做引用覆盖校验；`uncited_claims` 保留字段但固定为空，页面不再展示缺引诊断。模型写了 `[E#]` 就展示对应引用，没写则引用列表为空。引用校验逻辑仅保留给离线评测，详见 [引用校验回归记录](CITATION_VALIDATION.md)。

“停止生成”和“删除会话”使用 AbortController 取消读取；异步生成器关闭上游 HTTP 连接。检索在线程池运行，已开始的本地检索会完成，但取消后的请求不会继续进入模型生成。用户消息在开始生成时即以 `pending` 落库，停止/失败后变为 `aborted/failed`，刷新后仍可见；前端隔离请求状态，不完整草稿不会污染下一轮上下文。会话列表支持多会话切换、重命名、置顶和软删除。

## Markdown

支持标题、粗体、斜体、删除线、嵌套列表、引用、表格、代码块和链接。Marked 与 DOMPurify 固定版本随包提供；渲染前清理 HTML，禁止脚本、事件属性、表单和自动加载外部图片。表格与代码块可横向滚动，正文保持移动端宽度。

## 验证

运行 `scripts/check.ps1` 检查 Python 静态规则、类型、完整测试集；安装 Node.js 时同时检查前端语法及 `scripts/test-stream.mjs`。服务端测试使用 httpx 本地模拟传输，验证首个增量在后续内容读取前到达、Unicode、token 用量、直接交付、截断、超时、错误、取消连接清理及原 JSON 接口兼容。前端流测试覆盖 SSE 拆包、CRLF、非法 JSON 和完成后停止读取。

浏览器集成测试使用本机无界面 Edge 和本地虚构 SSE 服务，禁止外部请求：

```powershell
npm install --prefix data/frontend-deps --ignore-scripts --no-audit --no-fund playwright
node scripts/test-chat-ui.mjs
```

已验证生成中的正文增量、Markdown 各主要元素、危险 HTML/链接清理、桌面/390px 移动端布局、引用折叠、停止、删除、断流、多会话切换和访客隔离。截图保存在本地 `data/reports/multisession-mobile.png`。测试不发送本地史料，也不将模拟流结果称为真实 DeepSeek 联网验收。

本次完整检查通过：Ruff、mypy、198 项 Python 测试、3 项前端流解析测试，以及上述无界面浏览器集成测试。

流协议依据 [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)：仅输出 `delta.content`，记录 finish reason 和 usage，收到 `[DONE]` 且正常结束后进入最终交付。
