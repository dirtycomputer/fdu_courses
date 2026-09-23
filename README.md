# 复旦蹭课指南

复旦大学全校开课查询工具:课程列表 + 课表日历,纯静态页面,免登录。

**数据来源**:复旦大学教务服务系统「全校开课查询」公开接口(`fdjwgl.fudan.edu.cn`,免登录)。
教学大纲链接同样免登录,可直接查看。

## 功能

- **搜索**:按课程名 / 课程代码 / 教师姓名关键字搜索(支持多关键字)
- **筛选**:校区(邯郸/枫林/张江/江湾/其他)、开课单位、学位类型(本科/研究生/本研融通)、课程层级,可自由组合
- **按星期筛选**:点「周一~周日」快速只看某天有课的课程
- **教学大纲**:已公开大纲的课程,点「大纲 ↗」直接查看
- **课表日历**:周 × 节次网格,格子显示该时段开课门数,颜色越深课越多
  - 按 1~18 周切换,单双周排课自动区分
  - 表头显示星期 + 具体日期,节次旁标注上课时间
  - 「今」字高亮今天所在列;已过去的时段淡红色显示(过去整天整列标红,当天按节次结束时间精确标红)
  - 点击任意格子查看该时段所有开课课程(含跨节次长课),弹层内可继续按学位类型 / 校区 / 开课单位筛选
- 从列表切回日历,自动定位当前周
- 链接 `?view=cal` 直达日历视图(可加 `&w=3` 指定周次),适合手机收藏
- 手机端适配:表格、日历小屏内左右滑动

## 目录结构

```
docs/               静态站点(GitHub Pages 根目录)
├── index.html
├── app.js
├── style.css
└── data/latest.json   课程数据(由抓取脚本生成)
fetch/
└── fetch.py           数据抓取脚本(Python 3 标准库,无依赖)
server/
├── db.py              SQLite 连接
├── import_data.py     latest.json → SQLite
├── query_contract.py  LLM 查询 JSON 校验
├── queries.py         结构化课程查询
└── mcp_server.py      MCP tools
api/
└── index.py           Vercel ASGI / Streamable HTTP MCP 入口
vercel.json            Vercel 构建、Function 与路由配置
```

## 更新数据

每学期(或想刷新数据时)运行:

```bash
python3 fetch/fetch.py --semester 527 --name "2026-2027学年1学期" --start 2026-09-07
```

| 参数 | 说明 | 默认 |
|---|---|---|
| `--semester` | 教务系统学期 ID | 527 |
| `--name` | 学期显示名 | 2026-2027学年1学期 |
| `--start` | 第 1 周周一日期 | 2026-09-07 |
| `--out` | 输出路径 | docs/data/latest.json |

学期 ID 在[全校开课查询页](https://fdjwgl.fudan.edu.cn/student/for-all/lesson-search)的学期下拉里,可通过查看页面源码获取。

脚本会请求 7 次(全量 + 5 个校区归属 + 大纲标记),约 2~3 分钟,输出约 5MB JSON。

## 本地运行

因浏览器对 `file://` 下 fetch 的限制,需起一个静态服务:

```bash
python3 -m http.server 8765 --directory docs
```

访问 <http://localhost:8765>。

## AI / MCP 查询

课程数据可以导入 SQLite,再通过 MCP 暴露给 ChatGPT、Claude、Cursor 等支持 MCP 的客户端。模型只负责把自然语言转换成结构化筛选参数,课程匹配、周次和节次判断由 SQLite 完成。

### AI 工具查询指令

在静态页面选择“AI工具查询指令”，输入需求并复制 Prompt。由所选 AI 工具自身的 LLM 理解需求，生成符合 `docs/query-schema.json` 的 JSON，再调用 `POST /api/courses` 或 `GET /api/courses?filters=<编码后的JSON>`。服务端仅校验并执行，不做正则或关键词式自然语言解析，也不需要另外配置 LLM API key。

例如“查询黄萱菁老师的所有课程”应由模型生成 `{"teacher":"黄萱菁","limit":50}`，不将“所有”作为课程关键词。无法访问接口的 AI 仍可生成 JSON，用户可粘贴回页面生成接口链接。未知字段、错误类型及矛盾区间会返回 400；多页查询通过 `offset` 和 `has_more` 完成。

**接口迁移**：旧 `/api/ask?q=自然语言` 和 `POST /api/ask {"query":"..."}` 已移除；`/api/ask` 仅保留为结构化 JSON 的兼容 URL。调用方需改为先由 LLM 生成 JSON。完整协议见 [API.md](API.md)。

### 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell 激活虚拟环境时使用 `.venv\Scripts\Activate.ps1`。

### 生成 SQLite 数据库

```bash
python -m server.import_data
```

默认读取 `docs/data/latest.json`,输出 `data/courses.db`。也可以指定路径:

```bash
python -m server.import_data --source docs/data/latest.json --out data/courses.db
```

每次刷新课程 JSON 后重新运行一次导入即可:

```bash
python3 fetch/fetch.py --semester 527 --name "2026-2027学年1学期" --start 2026-09-07
python -m server.import_data
```

### MCP tools

当前暴露两个只读工具:

- `search_courses`:按课程/教师关键词、院系、校区、学位类型、学分、星期、节次、教学周、教学大纲、是否未满员进行组合查询。
- `get_course`:按教学班 ID、教学班代码或课程代码读取完整课程信息和上课安排。

时间参数约定:

- `day`:1=周一,...,7=周日
- `period_start` / `period_end`:1~14 节
- 同时给出起止节次时,按课程时段与目标时段是否重叠判断
- MCP 指令中约定下午通常为第 6~10 节,晚上通常为第 11~14 节

### 本地 stdio MCP

```bash
fdu-courses-mcp
```

也可以直接运行:

```bash
python -m server.mcp_server
```

### Streamable HTTP / 自建远程 MCP

```bash
export FDU_MCP_TRANSPORT=streamable-http
export FDU_MCP_HOST=0.0.0.0
export FDU_MCP_PORT=8000
export FDU_MCP_ALLOWED_HOSTS='mcp.example.com,mcp.example.com:*'
fdu-courses-mcp
```

MCP endpoint 为 `/mcp`,例如 `https://mcp.example.com/mcp`。

如果浏览器客户端会发送 `Origin`,可额外配置:

```bash
export FDU_MCP_ALLOWED_ORIGINS='https://example.com'
```

部署真实域名时应显式配置 `FDU_MCP_ALLOWED_HOSTS`,不要依赖本地 localhost 默认值。

### Vercel 一键部署远程 MCP

仓库已包含 `api/index.py` 和 `vercel.json`,可直接将仓库导入 Vercel,或在仓库根目录运行:

```bash
npm i -g vercel
vercel
vercel --prod
```

Vercel 构建阶段会执行:

```bash
python -m server.import_data
```

把 `docs/data/latest.json` 预生成成 SQLite 并打包到 Python Function。若本地 `vercel dev` 或异常构建情况下没有预生成数据库,`api/index.py` 会自动在 `/tmp` 中生成一次作为后备。

部署后有两个公开入口:

- `https://<deployment>.vercel.app/mcp` — MCP Streamable HTTP endpoint
- `https://<deployment>.vercel.app/health` — 健康检查与课程数据版本

Vercel 入口使用 `stateless_http=True` + JSON response,适合 Serverless/Fluid Compute。Vercel 已在公网反向代理层控制 Host/TLS,因此 `api/index.py` 仅对 Vercel 部署入口关闭 MCP SDK 面向 localhost 的 DNS-rebinding Host 检查;本地/自建 `server.mcp_server` 仍保留显式 Host allowlist 配置。

课程数据更新后只需提交新的 `docs/data/latest.json`;Vercel 下一次部署会重新生成 SQLite。

### 测试

```bash
pip install -e '.[test]'
python -m unittest discover -s tests -v
```

前端指令与交互回归测试（已在 Node.js 24.19 验证）：

```bash
npm --prefix tests ci
npm --prefix tests test
```

查询格式以 `server/query-schema.json` 为准；更新时同步 `docs/query-schema.json`，测试会校验两者一致。

自然语言示例:

> 找周三下午张江校区、3 学分以上、本科生能上的计算机相关课程。

模型可以将其转换为类似以下工具参数:

```json
{
  "keyword": "计算机",
  "campus": "张江校区",
  "biz_type": "本科",
  "min_credits": 3,
  "day": 3,
  "period_start": 6,
  "period_end": 10
}
```

## 部署

静态网页仍可使用 GitHub Pages:仓库 Settings → Pages → Source 选 `main` 分支 `/docs` 目录。

AI/MCP 服务建议直接部署到 Vercel,连接 URL 使用生产域名的 `/mcp`。
