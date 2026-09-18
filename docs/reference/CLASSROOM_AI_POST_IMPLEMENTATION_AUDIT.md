# 课堂 AI 严格实施后审计

审计日期：2026-09-09  
审计范围：当前工作区新增 `classroom/`、相关配置/测试/文档/脚本，以及实际 `dist/openwebui-classroom-review-windows-x64/` 中的自有组件与被依赖的 Open WebUI 运行路径。  
验收依据：[原实施计划](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md)（2026-09-08，v1.0）。目标基线：Windows x64、Open WebUI 0.11.2、便携 Python 3.11.9。  
配套交付：[475 项合规映射表](E:/codex-work/sub2api/CLASSROOM_AI_AUDIT_CHECKLIST.md)。本报告是审计结果，不是新设计或已经完成的修复。

## 1. 执行摘要

**结论：不具备生产可用性，不应通过本轮验收。** 当前成果是有一部分可靠领域逻辑的集成原型。主要风险不是缺少界面润色，而是实际启动和调用链尚未成立：完整 WebUI 启动存在导入问题；课堂页面/API 被根 SPA 挂载遮挡；正常教师和学生聊天被统一封锁；另一些原生兼容入口仍可绕过审批；教师批准的任务没有正在运行的服务派发器。

发现 **32 个整改主题：1 Critical、21 High、8 Medium、2 Low**。每项均列出位置、原计划关联、证据、影响、复验办法和修复建议。一个主题可能关联多个要求，避免把同一个根因拆成大量重复缺陷。H21 的 LAN HTTP 问题由代码和安全上下文标准支持，尚未做真实学生浏览器复现；M02 的 CSRF 部分是确认缺少控制、未证实完整远程利用；H20 的递归打包风险也没有主动执行。其余“已复现”仅指明确标记的隔离探针，不代表已攻击当前运行系统。

原计划十二项总验收结果为 **0 PASS、8 PARTIAL、4 FAIL**：

- 严格验收通过率：**0/12 = 0%**。
- 为保留对已有成果的描述，按 PARTIAL 折半计算的进度指标：**33.3%**。它不是代码完成比例，也不代表可上线概率。
- 核心已有的 **30 个测试全部通过**；另一个使用文件 SQLite 的 30 名模拟学生测试得到 30 次唯一派发、实际峰值并发 4、每人 used=1/reserved=0、30 条最终结算。这证明正常核心事务有价值，不能抵消原生集成、安全和失败恢复的反例。

审计期间没有修改应用源码、配置、现有账号库、聊天库或审批库，没有设置迁移 verified 标记，没有调用真实提供商或在真实数据上运行破坏性测试。只在临时目录执行独立测试/模拟，并新增本报告与检查表。

## 2. 整体实现质量及核验范围

### 2.1 质量判断

| 维度 | 判断 | 依据 |
|---|---|---|
| 需求理解 | 部分正确 | 保留预留/正式使用分离、拒绝扣次、独立名册和附件快照；误把“持久化正文”当成“已交付回答”，错误流收费违反 R05/R06。 |
| 领域核心 | 可保留并继续修复 | 参数化 SQL、短写事务、单 claim、唯一终态结算和部分幂等测试有效。不是必须推倒重写。 |
| 原生集成 | 不合格 | 准确版本的导入路径、根 SPA 顺序、同步 Pipe 调用、模型 ID 和原生登录 hook 没有完成契约验证。 |
| 权限与身份 | 不合格 | URL 拒绝列表不完整，教师也被挡；旧原生 JWT 可以懒登记，首次改密/重置流程不安全，WS 未覆盖。 |
| 执行与恢复 | 不合格 | 独立服务无调度生命周期；截断误判成功；停止不取消执行；恢复/过期函数没有运行调用者。 |
| 数据留存/运维 | 不合格 | 旧聊天和审批没有迁移；备份不含原生库；恢复先覆写后验证；缺完整便携包和可执行回滚。 |
| 测试与交付陈述 | 不足 | 测试集中在直接调用类或另一份独立 API；“完成”声明没有覆盖真正上线入口。 |

### 2.2 已检查的改动和基线

当前 Git 状态显示 `.gitignore` 修改，原计划和 `classroom/` 尚为 untracked；未发现承载本次完整实现的独立提交。因此审计以当前文件内容为准，而不是假设有一份完整提交 diff。没有看到对主仓库 Go/Vue 业务的相关改造。

已阅读课堂应用、桥接、Pipe/Filter、两张页面、全部新增测试、DDL/迁移、账号模板、导出样例、依赖锁、兼容清单、基线说明、教师指南和 PowerShell 脚本，并沿实际便携 Open WebUI 的认证、文件、函数执行、聊天别名和静态挂载代码跟踪调用。没有逐文件审计全部第三方依赖；审计范围是本次变化及其实际依赖的集成路径。

核对发行目录时，31 个新 app 文件、9 个脚本与源码对应副本一致；页面却放在 `app/web/`，launcher 寻找的是 `bundle/web/`。原审核服务/Filter/页面及旧教师说明仍留在解压目录。只有旧 v1.0.0 ZIP，没有完成后的新 Windows 全量包。基线目录只有 hash manifest，缺少 README 宣称的原样源码快照。锁文件的少量版本 pin 与现有库一致，但不具备完整依赖和安装包哈希锁。

现有数据库仅只读检查。公开注册和部分自动任务的持久配置仍为开启状态，说明“已完成配置迁移并验证关闭”没有证据；这不表示本轮改动已经把现场部署切换成功。正常 launcher 默认拒绝未验证原生迁移的行为应保留，不能靠人工设置 marker 跳过验收。

### 2.3 实际调用链结果

| 工作流 | 当前实际结果 | 关键问题 |
|---|---|---|
| 中文 CMD / Start → 便携 Python → WebUI | 隔离解释器忽略 PYTHONPATH；自有桥接导入不可用，空格路径还会拆参数 | H01、H19 |
| WebUI → /classroom 与 /api/classroom | root SPA 先注册；GET 落到 HTML，POST 返回 405；页面在发行目录还错位 | H02 |
| 原生聊天 → Pipe | 正常聊天被 middleware 全拒；Pipe ID/操作 metadata 没接；同步 Pipe 会阻塞事件循环 | H03、H05 |
| 页面提交 → 教师批准 → 执行 | submit/decision 只写 DB；运行服务没有 worker/background scheduler | H04 |
| 其他原生模型入口 → 上游 | messages/embeddings 的实际 handler 可越过当前拒绝列表，未建课堂请求仍有出口调用 | C01 |
| 初始密码/重置 → 新会话 | 原生成功登录没 hook，旧 JWT 可懒登记；同密码/原生 false 成功判定不严 | H06—H08 |
| 回答流 → 停止/重启 → 额度 | 截断当完成、未交付也扣次、真实调用未取消、恢复辅助函数未自动调用 | H09—H11 |
| 附件 → 审核 → 追问 | 教师无法读取实际附件，原生文件未接管，后续历史来自浏览器 | H14、H15 |
| 教师导出 → 全备 → 恢复 | 新请求有局部导出；旧聊天遗漏，全备不全，坏备份先毁目标后报错 | H16—H18 |

### 2.4 独立验证记录与证据边界

| 证据 | 执行方式 | 结果及能够证明的范围 |
|---|---|---|
| T01 现有测试 | 用便携 Python 3.11.9 执行业务与 FastAPI 测试；额外加载系统 pytest 纯 Python 测试依赖，关闭自动插件、字节码和 pytest cache；测试原样复制到临时目录以避免环境目录扫描 | 30 passed，1 个 Starlette/httpx 弃用警告。首次在工作区直接收集误入 E:/WpSystem，属于测试环境问题，改为隔离收集后通过。测试没有被修改。 |
| T02 原生出口 | 编译包内实际 embeddings、messages/Anthropic handler 和依赖调用片段，接实际 middleware；仅替换身份、配置及提供商网络 I/O | /api/embeddings、/api/v1/messages、/api/message 返回 200，模拟出口有调用，课堂请求数 0。Anthropic 分支使用支持该模式的模拟连接。 |
| T03 路由顺序 | 使用包内实际 SPAStaticFiles 类，按原顺序 mount root 后调用真实 install_native_routes | /me GET 返回 text/html；requests POST 405；学生页返回原生 SPA。没有启动真实用户数据上的完整 WebUI。 |
| T04 原生课堂 API | 真实 native_routes/TestClient；依赖提供固定已验证测试用户，原生密码 I/O 为模拟 | 重置后未登记旧 token 可用；已登记 token 超 12 小时仍用；必改上传 200；同密码且原生 HTTP 200 false 也清标记；相同调额 header 重放产生 +2。 |
| T05 流解析 | 真实 HttpUpstream，将 urlopen 替换为内存 SSE 响应 | partial 后 EOF、SSE error、空 HTTP 200 均 completed/charge=1。没有模型费用。 |
| T06 取消与派发 | 可控阻塞模拟提供商；真实 service/worker；记录实际存活调用而非仅 DB 状态 | 无消费者读取但写 delta 后停止扣 1；max_concurrency=1 时停止第一问再派第二问，实际峰值达到 2。 |
| T07 生命周期/授权 | 临时文件库、可注入时钟、重建 Service；approve 和 claim 间改变学生/模型状态 | 昨日 pending 在只读查询后不清理；重启遗留 generating/reserved=1 且 ready；暂停学生仍派发；移除模型再批准仍发送旧模型。 |
| T08 附件/备份/校验 | 合成图片/文本、模拟原生库、故意损坏的备份；仅操作临时目录 | 假 PNG 被接收、有效 VP8L WebP 被拒；备份漏 webui.db；restore 失败前已替换旧文件；verify_only 创建新 DB。 |
| T09 便携入口 | 包内隔离解释器只读 import 路径探针；同样 Start-Process 参数构造运行无副作用 argv 脚本 | isolated=1/ignore_environment=1，自有模块不可发现；中文空格路径参数被截断、退出码 2。 |
| T10 正常 30 人核心并发 | 临时文件 SQLite，30 个不同学生提交并批准，8 个 worker 竞争，配置上游并发 4 | calls=30、unique request IDs=30、峰值=4、每人 used=1/reserved=0、最终结算=30。只覆盖正常核心流程，不是 30 浏览器/校园网/p95 验收。 |
| T11 内容与声明 | 逐文件/哈希比对源码与解压目录，只读 DDL、路由、配置和指南 | 确认产物布局、缺失路径/调用者及完成声明偏差；关键文件审计哈希见末尾。 |

除现有 30 个测试外，上述探针未作为产品测试代码写回仓库。各问题的“如何验证”给出复验场景和预期断言，整改时应把必要场景补入正式测试。

没有执行：真实提供商调用、生产压力/断网、现有数据库迁移、真实账号重置、干净 Windows、新发行 ZIP 安装、30 个浏览器延迟测试、真实浏览器 CSRF/导出脚本执行测试。没有把这些未测项描述为通过。为隔离缺陷，部分探针单独接入 native_routes，绕过了已经确认的根 SPA 遮挡；这些是修复挂载后仍会出现的独立问题，不是声称当前不可达端点已经被远程利用。

## 3. 原计划合规百分比

分母采用原计划 L 节明确给出的十二项总验收，避免把一个需求在 R/C/D/E/K 中反复出现当作多次得分。PASS=1、PARTIAL=0.5、FAIL=0、NOT VERIFIED=0 仅用于辅助进度；严格合规只计 PASS。

| 原总验收项 | 状态 | 主要依据 |
|---|---|---|
| 1. 所有学生可用模型能力均不能跳过审批与额度。 | **FAIL** | 存在实际非授权出口调用（C01）。 |
| 2. 教师拒绝扣 1 次；正常成功扣 1 次；意外中断零次；有回答后学生主动停止扣 1 次。 | **PARTIAL** | 拒绝/正常成功核心正确；截断和主动停止分类错误（H09、H10）。 |
| 3. 同一操作最多一个预留、一个最终结算、一个对外派发。 | **PARTIAL** | 正常核心 reserve/attempt/settle 唯一；原生操作恢复与真实执行链未完（H03—H05、H11）。 |
| 4. 教师机时区的日界正确，跨日待审移出队列但保留全部历史。 | **PARTIAL** | 日桶算法存在；自动过期、时区异常保护失败（H11、M06）。 |
| 5. 单人和全班批量调整可用，历史不可被清零。 | **PARTIAL** | 核心批量正确；UI/API 幂等/全选/自定义不全（H13、M08）。 |
| 6. 批量账号强制首次改密、教师重置可用，旧令牌确实失效。 | **FAIL** | 首次改密/重置和旧 JWT 撤销失败（H06—H08）。 |
| 7. 图片与 .py 等文本文件真实可审、实际送模内容一致。 | **PARTIAL** | 有不可变文件核心；教师不能审实际附件、原生文件未接（H14）。 |
| 8. 永久对话/附件归档及教师导出可用，学生删改不破坏留存。 | **PARTIAL** | 新课堂归档存在；旧对话/完整会话和导出缺失（H16）。 |
| 9. 30 人并发、服务重启、网络中断、双决策和幂等重试测试通过。 | **PARTIAL** | 30 个核心测试及独立 30 人模拟通过；完整恢复/网络/原生 UI 关键矩阵失败或未测。 |
| 10. 现有用户 ID、旧聊天、附件、审批完整迁移；没有追扣旧记录。 | **FAIL** | 没有用户/旧聊天/附件/审批的完整迁移（H20）。 |
| 11. 便携包可换盘、中文路径运行，干净机器无额外依赖下载。 | **FAIL** | 完整启动、空格路径失败且没有最终发行包（H01、H19、H20）。 |
| 12. 备份恢复和受保护回滚已演练，发行包不带真实数据或秘密。 | **PARTIAL** | 局部备份/导出存在；全备恢复、回滚和安全新包验收未通过（H17、H18、H20）。 |

**严格通过率 0%，辅助进度 33.3%。** 没有改变原计划的业务规则来提高分数。[475 项合规映射表](E:/codex-work/sub2api/CLASSROOM_AI_AUDIT_CHECKLIST.md)共有 475 行（PASS 58、PARTIAL 247、FAIL 162、NOT VERIFIED 8），用于全面追踪，含重复语义和字段级项目，不参与上述分母。

## 4. Critical 与 High 缺陷

以下是本轮审计编号。它们与原计划 B 节同名编号不是同一套编号；“关联计划”给出对应原要求。严重性按数据、安全及核心课堂功能的影响评定，不由能否临时手工绕过启动故障决定。

<a id="C01"></a>

### C01 · Critical · 公开兼容入口仍能绕过审批、额度和课堂会话

- **位置：** [classroom/app/openwebui_bridge/middleware.py:15](E:/codex-work/sub2api/classroom/app/openwebui_bridge/middleware.py:15)；[classroom/app/bootstrap_openwebui.py:105](E:/codex-work/sub2api/classroom/app/bootstrap_openwebui.py:105)；[dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/main.py:1049](E:/codex-work/sub2api/dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/main.py:1049)；[dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/main.py:1975](E:/codex-work/sub2api/dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/main.py:1975)。
- **关联计划：** B/C01、C02；C2；E5；H2；K2；总验收第 1 项。
- **证据：** 已复现：把包内原始 embeddings、generate_messages 和 Anthropic passthrough handler 接到实际中间件，仅替换身份/配置依赖和提供商 I/O。/api/embeddings、/api/v1/messages、/api/message 均返回 200，录到出口调用，课堂请求数为 0。

**问题：** 实际拦截列表遗漏上述别名；generate_messages 可以直接透传提供商，也可以在 Python 内调用 chat_completion，后者不会重新经过 HTTP URL 中间件。原生 /api/v1/files 上传也没有强制 process=false。bootstrap 会关闭旧 Filter，却没有迁移并清除普通提供商密钥或关闭所有副调用。localhost + X-Classroom-Bootstrap 的永久豁免还覆盖了所有被列入的模型路径。

**影响：** 具备原生登录权限的学生可以走另一入口调用可访问的提供商，完全不经过教师审批和每日三次限制。上传处理也可能触发未经审批的嵌入/转写。不能把普通聊天返回 403 当成出口已经封闭。

**如何验证/复现：** 在隔离环境配置一个学生可访问的模拟提供商，携带有效原生学生令牌分别调用这些别名，断言实际模型/嵌入出口调用数必须为 0。Anthropic 透传复现使用支持该模式的模拟连接；未调用当前真实提供商。

**建议修复：** 先完成唯一出口及可信身份适配，再移除旧保护；从准确版本实际路由表建立能力清单，覆盖别名、内部调用、副任务和上传处理。真实凭据仅由受管执行服务持有；启动与配置变更时验证这些条件。引导豁免应是一次性、认证且仅限安装操作的权限。

<a id="H01"></a>

### H01 · High · 便携启动器没有把课堂模块加入隔离 Python 的搜索路径

- **位置：** [classroom/app/run_openwebui.py:53](E:/codex-work/sub2api/classroom/app/run_openwebui.py:53)；[classroom/scripts/Start.ps1:22](E:/codex-work/sub2api/classroom/scripts/Start.ps1:22)；[dist/openwebui-classroom-review-windows-x64/runtime/python/python311._pth:1](E:/codex-work/sub2api/dist/openwebui-classroom-review-windows-x64/runtime/python/python311._pth:1)。
- **关联计划：** H2；I1、I2；L1、L8、L9。
- **证据：** 运行包内 Python，设置与 Start 相同的 PYTHONPATH 后，isolated=1、ignore_environment=1；find_spec('openwebui_bridge') 和 find_spec('classroom_service') 均为 False。

**问题：** run_openwebui.py 直接导入顶层课堂模块，未像 api_classroom.py 等入口那样插入 app 目录。便携解释器的 ._pth 隔离模式忽略 PYTHONPATH；Open WebUI 自身也没有替它注册课堂 app 路径。

**影响：** 即使人工补齐迁移标记，完整 WebUI 启动仍会在桥接模块导入处失败。已验证的 -NoOpenWebUI 路径无法证明完整启动可用。

**如何验证/复现：** 使用原包解释器、原 ._pth 和原启动目录运行完整 launcher 的隔离副本；在首次自有模块导入前检查 sys.path。不要用已经手工插入源码目录的开发测试替代。

**建议修复：** 在准确版本 launcher 最早阶段显式注册相对 app 路径，或把自有模块作为可重复安装的包加入便携运行时；对原始解释器执行完整启动契约测试。

<a id="H02"></a>

### H02 · High · 课堂路由被 Open WebUI 的根静态挂载遮挡，发行目录还放错了页面位置

- **位置：** [classroom/app/run_openwebui.py:65](E:/codex-work/sub2api/classroom/app/run_openwebui.py:65)；[classroom/app/openwebui_bridge/native_routes.py:38](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:38)；[classroom/app/openwebui_bridge/native_routes.py:276](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:276)；[dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/main.py:3037](E:/codex-work/sub2api/dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/main.py:3037)。
- **关联计划：** C2 第 6 项；E2、E3；F；G；H2；L6。
- **证据：** 使用包内实际 SPAStaticFiles 类和实际路由安装器复现：GET /api/classroom/v1/me 返回 200 text/html；POST /api/classroom/v1/requests 返回 405；/classroom/student/ 返回原生 SPA，而不是课堂页面。

**问题：** 导入 open_webui.main 时根路径 / 已经挂载，之后追加的课堂 mount/router 排在其后。另已逐文件核对：发行目录页面在 app/web 下，run_openwebui.py 寻找 bundle/web，后者不存在。

**影响：** 教师和学生页面/API 不可正常使用；浏览器可能把 HTML 当 JSON 解析，表现为加载失败或空数据。

**如何验证/复现：** 保留原生根挂载顺序，安装课堂路由后用 TestClient 或浏览器访问上述三个路径；同时核对实际打包后的 web_root 是否存在。

**建议修复：** 在根 SPA 挂载之前注册课堂路由/页面，或采用经过测试的明确路由重排；统一源码与发行包布局，并对最终目录做 GET/POST 内容类型与页面标识验收。

<a id="H03"></a>

### H03 · High · 正常聊天及教师管理被统一封锁，Pipe 的模型和操作标识也未接通

- **位置：** [classroom/app/openwebui_bridge/middleware.py:24](E:/codex-work/sub2api/classroom/app/openwebui_bridge/middleware.py:24)；[classroom/app/openwebui_classroom_pipe.py:28](E:/codex-work/sub2api/classroom/app/openwebui_classroom_pipe.py:28)；[classroom/app/openwebui_classroom_pipe.py:62](E:/codex-work/sub2api/classroom/app/openwebui_classroom_pipe.py:62)；[classroom/app/bootstrap_openwebui.py:24](E:/codex-work/sub2api/classroom/app/bootstrap_openwebui.py:24)；[classroom/compatibility.json:5](E:/codex-work/sub2api/classroom/compatibility.json:5)。
- **关联计划：** R01、R03；C2、C3；E5；H2；L1、L6。
- **证据：** 代码确认。实际中间件不查询用户角色，直接拒绝正常聊天及 models/configs/functions 路由。包内 get_function_models 对单 Pipe 使用 Function ID，而 bootstrap 注册的是 classroom_pipe。

**问题：** 实际聊天模型 ID 是 classroom_pipe，策略和 UI 却使用 classroom-default，没有别名映射。Pipe 要求 classroom_operation_id，但没有原生前端补丁或可信适配代码注入它。RouteGuard 中允许教师/受管聊天的逻辑没有成为实际 ASGI 判定。

**影响：** 学生无法保留原生聊天流程；教师也失去要求保留的模型、配置和函数管理能力。只安装一个 Function 不等于完成聊天集成。

**如何验证/复现：** 在隔离部署中用教师与学生分别请求原生正常聊天、模型设置；检查实际 /api/models 的 Pipe ID，再从正常 UI 发起请求并查看可信 metadata。

**建议修复：** 把角色校验、受管模型映射、稳定操作 ID、会话/消息关联真正接入正常聊天；教师保留管理权限，学生仅能使用受管能力。先通过 L1 的完整入口契约，再开放其他阶段。

<a id="H04"></a>

### H04 · High · 教师批准后的请求没有运行中的派发器，服务分工与 readiness 均未落地

- **位置：** [classroom/app/classroom_service/api.py:230](E:/codex-work/sub2api/classroom/app/classroom_service/api.py:230)；[classroom/app/openwebui_bridge/native_routes.py:95](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:95)；[classroom/app/openwebui_bridge/native_routes.py:144](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:144)；[classroom/app/openwebui_classroom_pipe.py:36](E:/codex-work/sub2api/classroom/app/openwebui_classroom_pipe.py:36)；[classroom/app/classroom_service/service.py:637](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:637)；[classroom/app/openwebui_bridge/integration.py:40](E:/codex-work/sub2api/classroom/app/openwebui_bridge/integration.py:40)。
- **关联计划：** C2、C5；D1、D6；E4；H2；I2；L1、L4。
- **证据：** 调用链确认：API 启动没有创建 worker 或调度任务；submit/decision 只写状态。生产代码唯一调用 worker.run_one 的位置位于当前不可达的 Pipe 等待循环。ClassroomIntegration 没有被 launcher 调用。

**问题：** 8790 服务、原生桥接和 Pipe 各自创建 ClassroomService，后两者直接访问同一个 DB；内部 HMAC 协议只实现了 readiness，没有提交、会话、心跳等协议。提供商调用和密钥回到 WebUI 进程。ready_report 仅检查本地布尔值与 SQLite quick_check，甚至没有执行器也报告 ready=true。缺少受管提供商配置迁移、模型别名/图像能力和课堂提示词的实际配置链。

**影响：** 自建页面提交并批准后会一直停在 approved_queued；教师会看到虚假的“保护链已就绪”。不同实例的模型策略版本和会话密钥还会分歧。

**如何验证/复现：** 通过实际外部课堂接口提交并批准一个模拟问题，不手工调用业务类 worker，检查出口记录与状态；关闭/删除 Pipe 或不配置上游后再次检查 readiness。

**建议修复：** 实现计划要求的唯一执行所有者及调度生命周期，打通经过认证的内部协议；统一配置与策略事实源。readiness 必须验证真实桥接、执行器、版本、受管模型和旁路拒绝，并在不满足条件时关闭学生生成。

<a id="H05"></a>

### H05 · High · 同步 Pipe 等待会阻塞 Open WebUI 事件循环

- **位置：** [classroom/app/openwebui_classroom_pipe.py:54](E:/codex-work/sub2api/classroom/app/openwebui_classroom_pipe.py:54)；[classroom/app/openwebui_classroom_pipe.py:75](E:/codex-work/sub2api/classroom/app/openwebui_classroom_pipe.py:75)；[dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/functions.py:157](E:/codex-work/sub2api/dist/openwebui-classroom-review-windows-x64/runtime/python/Lib/site-packages/open_webui/functions.py:157)。
- **关联计划：** C5；D6；G1；H2；K5 的延迟/并发目标；L4。
- **证据：** 准确版本调用链确认：execute_pipe 对同步函数直接执行 pipe(**params)，不进入线程池；该 Pipe 同步轮询并 time.sleep(1)，上限默认 86400 秒。

**问题：** 等待审批、运行同步 HTTP 提供商和轮询都发生在同一 WebUI 事件循环中。Pipe 只在完成后返回 choices.message 字典，没有持续输出持久化 delta；原生 stream 分支对字典原样发送一帧。

**影响：** 一旦修复前面的路由问题，首个待审请求就可能阻塞同进程教师审批、登录和其他学生请求，形成无法审批的等待。流式回答/停止体验也不符合计划。

**如何验证/复现：** 在准确版本的 execute_pipe 路径下启动一个待审问题，同时请求教师队列或运行事件循环心跳；不能仅在独立线程里直接调用 Pipe 测试。

**建议修复：** 使用真正异步、可取消的等待和持久事件流；提供商执行由独立服务负责。按实际 Open WebUI 流式协议返回，并测试等待审批时其他接口仍可响应。

<a id="H06"></a>

### H06 · High · 旧令牌撤销和首次登录保护没有覆盖原生认证入口

- **位置：** [classroom/app/openwebui_bridge/native_routes.py:66](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:66)；[classroom/app/classroom_service/auth.py:111](E:/codex-work/sub2api/classroom/app/classroom_service/auth.py:111)；[classroom/app/openwebui_bridge/middleware.py:29](E:/codex-work/sub2api/classroom/app/openwebui_bridge/middleware.py:29)。
- **关联计划：** B/H08；D3；E5；H3；K2；总验收第 6 项。
- **证据：** 实际 native_routes、会话类复现：已登记的旧令牌撤销后 401；从未登记过但由原生依赖认定有效的旧令牌在重置后仍 200；已登记原生会话过 13 小时仍 200。实际中间件直接放行 websocket scope。

**问题：** 会话在首次访问课堂 API 时自动登记，而不是原生密码登录成功时登记。register_native_token 不检查登记记录的 expires_at。原生 signin/password/reset/signout、REST 及 /ws 没有课堂安全 hook；自签课堂令牌的 validate 测试不能代表原生令牌路径。

**影响：** 持有尚未进入课堂表的旧 JWT 的人可在重置后重新登记；退出/改密后的原生访问和上传仍可能有效，12 小时课堂会话上限失效。

**如何验证/复现：** 用两个合法原生会话，仅让 A 访问课堂，再重置密码；分别用 A/B 调用课堂与原生 REST/WS。推进可注入时钟超过 12 小时后重测。

**建议修复：** 只在可信原生登录成功事件登记令牌指纹/epoch/原生到期时间，禁止懒登记；统一验证所有受保护 REST/WS。原生改密、重置、退出、角色变化必须同步撤销，服务不可用时拒绝。

<a id="H07"></a>

### H07 · High · 首次改密可上传且可用相同密码解除限制，重置顺序不安全

- **位置：** [classroom/app/openwebui_bridge/native_routes.py:121](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:121)；[classroom/app/openwebui_bridge/native_routes.py:227](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:227)；[classroom/app/openwebui_bridge/native_routes.py:251](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:251)；[classroom/app/classroom_service/accounts.py:273](E:/codex-work/sub2api/classroom/app/classroom_service/accounts.py:273)。
- **关联计划：** R09；D3、D10；E2；H3；K4。
- **证据：** 实际 native_routes 复现：must_change_password=1 的学生上传返回 200。模拟原生接口返回 HTTP 200、正文 false，且新旧密码相同，课堂接口仍返回 200 并清除必改标记。包内原生改密接口确实返回 bool。

**问题：** student 依赖没有限制首次会话只能访问改密/退出等入口；首次改密接口没有应用账号服务中的新旧密码不同/最短长度检查，也未检查原生操作的布尔成功值。教师重置先修改原生密码，再提升 epoch；没有 reset_in_progress 保护。

**影响：** 统一初始密码可能继续使用；失败的改密也可被记成已完成。重置中途失败/崩溃会留下安全状态不一致窗口。原生界面的重置则完全不更新课堂状态。

**如何验证/复现：** 按上述三个独立条件测试：必改状态上传；新旧密码相同；原生返回 200 false/重置后课堂写入失败。全部使用隔离账号与模拟原生适配器。

**建议修复：** 把必改会话限制放在统一认证边界；统一调用经过校验的账号生命周期；先锁定并撤销旧会话，再执行原生重置，成功后完成状态。检查真实成功结果，失败保持受限并提供幂等恢复。

<a id="H08"></a>

### H08 · High · 账号导入不支持可靠重放/崩溃恢复，过渡账号提前获得 user 角色

- **位置：** [classroom/app/classroom_service/accounts.py:74](E:/codex-work/sub2api/classroom/app/classroom_service/accounts.py:74)；[classroom/app/classroom_service/accounts.py:215](E:/codex-work/sub2api/classroom/app/classroom_service/accounts.py:215)；[classroom/app/classroom_service/accounts.py:243](E:/codex-work/sub2api/classroom/app/classroom_service/accounts.py:243)；[classroom/app/classroom_service/accounts.py:268](E:/codex-work/sub2api/classroom/app/classroom_service/accounts.py:268)。
- **关联计划：** D9、D10；E3；H3、H4；K4；L3。
- **证据：** 复现：已完成批次再次 commit 返回 ValidationError；全是无效行的批次 commit 返回 completed 且结果行数为 0。内存预览被清除/进程重启后没有重新附加源文件并恢复该批次的实现。

**问题：** 原生账号直接以 user 创建，之后才建立课堂状态；未采用 pending/provisioning 安全顺序。原生创建与记录 user_id 之间仍有崩溃窗口。commit 依赖内存密码预览；没有批次查询/恢复 API，也不完整返回无效行。异常补偿还可能删除刚创建但已被其他步骤使用的账号。

**影响：** 中断后可能出现无法接管的原生账号、重复邮箱冲突或名册与账号不一致；“部分失败可以重新提交未完成批次”的文档承诺不成立。

**如何验证/复现：** 分别在原生创建成功后、保存 user_id 前、enroll 后、返回结果前注入故障并重启进程，再重放同一批次。预览已有原生邮箱和全无效 CSV 也应有准确逐行结果。

**建议修复：** 按计划采用 pending 安全过渡和持久化的逐行操作状态；恢复时重新提供原文件但关联旧批次，核对原生账号身份并幂等接续。已完成批次返回保存结果，无效行不得被隐藏；避免未经确认删除账号。

<a id="H09"></a>

### H09 · High · 截断、错误和空响应被记为正常完成并扣次

- **位置：** [classroom/app/classroom_service/worker.py:58](E:/codex-work/sub2api/classroom/app/classroom_service/worker.py:58)；[classroom/app/classroom_service/worker.py:95](E:/codex-work/sub2api/classroom/app/classroom_service/worker.py:95)。
- **关联计划：** R05；C4、C5；D6；K1、K5；L4。
- **证据：** 调用真实 HttpUpstream，替换 urlopen 为内存响应：只有 partial delta 后 EOF、只有 SSE error、空 HTTP 200 三种情况均得到 completed、charge_units=1；后两种 output_text 为 null。

**问题：** 解析器忽略错误/无法解析的事件，迭代结束直接视为成功；没有区分有效完成标记与连接截断，也不验证响应类型和空/错误结果。

**影响：** 恰好违反用户明确要求的“意外中断不扣，即使已有部分回答”，并可能在没有回答时扣掉学生机会。

**如何验证/复现：** 模拟提供商分别返回上述三个响应，并记录请求状态、ledger 与 used；应全部为受控故障、零扣次和可追踪原因。

**建议修复：** 使用明确的流协议状态机校验正常结束、错误及截断；将真实完成信号传给 worker。持久化部分正文，故障释放预留；补充首输出/总生成超时与错误流测试。

<a id="H10"></a>

### H10 · High · 停止只结算数据库，未中断上游，且按未交付正文扣次

- **位置：** [classroom/app/classroom_service/service.py:419](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:419)；[classroom/app/classroom_service/service.py:572](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:572)；[classroom/app/classroom_service/service.py:602](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:602)；[classroom/app/classroom_service/worker.py:104](E:/codex-work/sub2api/classroom/app/classroom_service/worker.py:104)；[classroom/app/openwebui_bridge/native_routes.py:149](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:149)。
- **关联计划：** R06；C4、C5；D6；G1；K1、K2；L4。
- **证据：** 复现：从未读取事件的消费者，在服务写入一个 delta 后停止仍扣 1 次。阻塞模拟上游、并发配置为 1 时，停止第一问后提交第二问，两个提供商调用同时存在，峰值为 2。

**问题：** visible_output_bytes 只是持久化字节数，不是交付给有效订阅的正文；没有 delivered_seq/消费确认。cancel 立即结束数据库状态但没有取消 HTTP 连接/worker。worker 等下一个 chunk 才检查终态；pending→generating 竞争时 cancel 还会直接返回生成中状态而不停止。 原生桥接已有教师 stop 路由，但同样调用这个只改变数据库状态的 cancel；不能据此认为教师停止已生效。

**影响：** 学生没有收到回答也可能被扣次；停止后资源继续占用，实际上游并发能突破设置，计数/状态与执行不一致。

**如何验证/复现：** 使用可控阻塞提供商测试“无正文停止”“已持久化未交付停止”“等待 chunk 时停止”“排队转生成时停止”，并统计实际存活调用数。

**建议修复：** 把主动停止事件、交付序号、执行取消句柄和租约接通；真实上游结束前继续占用执行并发槽。以同一事务/状态版本处理停止竞争，重复停止返回同一结果。

<a id="H11"></a>

### H11 · High · 跨日过期和重启恢复只有辅助函数，没有接入运行生命周期

- **位置：** [classroom/app/classroom_service/service.py:35](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:35)；[classroom/app/classroom_service/service.py:403](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:403)；[classroom/app/classroom_service/service.py:532](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:532)；[classroom/app/classroom_service/service.py:624](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:624)；[classroom/app/classroom_service/api.py:230](E:/codex-work/sub2api/classroom/app/classroom_service/api.py:230)。
- **关联计划：** R07；C5、C6；D6；I2；K1、K5；L4。
- **证据：** 复现：跨一天后只执行 /me 对应查询、health 和待审列表，昨天的记录仍 pending；重建文件数据库上的 Service 后，旧 generating 仍 generating、reserved=1，但 ready=true。

**问题：** expire_pending 只由新提交、决定或 claim 触发；没有启动/定时/查询兜底。recover_after_restart 没有调用者；租约清理只在领取下一任务时触发；心跳函数没有生产调用路径。

**影响：** 跨日待审不会自动移出队列；重启后学生可能一直占用活动请求和额度，课堂却显示就绪。已有测试手动调用清理函数，掩盖了集成遗漏。

**如何验证/复现：** 创建待审/生成任务后仅模拟时钟推进或进程重建，不手动调用修复函数；通过正常接口观察状态和额度。

**建议修复：** 启动恢复事务完成后才能 ready；加入有界定时清理、请求/查询兜底、WebUI 消费心跳和实例协调。生成结果不明时零扣、不重发；已知未派发任务按计划恢复。

<a id="H12"></a>

### H12 · High · 派发时不重新检查学生权限和批准的模型配置

- **位置：** [classroom/app/classroom_service/service.py:194](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:194)；[classroom/app/classroom_service/service.py:369](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:369)；[classroom/app/classroom_service/service.py:505](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:505)；[classroom/app/classroom_service/service.py:566](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:566)。
- **关联计划：** C3 第 9—12 项；D5、D6；E3；K2；L4。
- **证据：** 复现：批准后暂停学生，worker 仍派发并完成。把允许模型改成 new-model 后，原请求回到待审；再次普通批准，实际仍发送已经移除的 classroom-default。

**问题：** claim_next 不重查 enrollment、ai_enabled、必改密/安全操作状态、原生角色或模型配置版本。普通 approve 使用原始快照且不核验当前白名单，也未更新配置绑定。effective_digest 保存但派发未核验；多个 Service 实例缓存的模型集合可能不同。

**影响：** 教师暂停、重置密码或移除模型不能可靠阻止已排队请求；“配置变化必须重新审核且绑定新快照”没有实现。

**如何验证/复现：** 在 approve 与 claim 之间分别改变学生状态、安全状态、模型策略和快照，断言不得继续发送失效授权。

**建议修复：** 在唯一领取/派发边界重新核对身份、暂停、配置版本及快照摘要；变化时明确退回待审/中断，重新批准必须选择合法配置并生成对应不可变快照。

<a id="H13"></a>

### H13 · High · 调额 HTTP 层丢弃幂等键、版本和日期，重传会重复加次

- **位置：** [classroom/app/openwebui_bridge/native_routes.py:159](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:159)；[classroom/app/classroom_service/api.py:174](E:/codex-work/sub2api/classroom/app/classroom_service/api.py:174)；[classroom/app/classroom_service/quota.py:119](E:/codex-work/sub2api/classroom/app/classroom_service/quota.py:119)；[classroom/web/teacher/index.html:22](E:/codex-work/sub2api/classroom/web/teacher/index.html:22)。
- **关联计划：** R08；C6；D7；E1、E3；F2；K1。
- **证据：** 实际 native_routes 复现：相同 Idempotency-Key 和相同 +1 请求提交两次，两次 200，adjustment=2。

**问题：** 页面把幂等键放在 HTTP 头，两个 API 实现都只读取 body.operation_key。页面没有提交预览版本/日期；管理器允许缺省版本并生成新 key。跨日的旧预览会改到新的自然日。

**影响：** 网络重传、重复点击或过期页面可造成未经教师确认的额外调额；核心类的幂等单测通过不代表实际 UI/API 幂等。

**如何验证/复现：** 通过教师实际接口重放相同头；预览后先由另一请求调整额度，再提交旧版本；午夜前预览、午夜后提交。

**建议修复：** 统一读取并强制 Idempotency-Key、日期和 expected_versions，前端持久化同一操作标识并提交预览结果；同键异体/旧版本/跨日均受控冲突，批量仍保持原子性。

<a id="H14"></a>

### H14 · High · 教师无法查看真实附件内容，原生附件路径未接入

- **位置：** [classroom/web/teacher/index.html:20](E:/codex-work/sub2api/classroom/web/teacher/index.html:20)；[classroom/web/student/index.html:18](E:/codex-work/sub2api/classroom/web/student/index.html:18)；[classroom/app/openwebui_bridge/native_routes.py:121](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:121)；[classroom/app/classroom_service/service.py:237](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:237)；[classroom/app/classroom_service/service.py:450](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:450)；[classroom/app/openwebui_classroom_filter.py:11](E:/codex-work/sub2api/classroom/app/openwebui_classroom_filter.py:11)。
- **关联计划：** R10；C3；E2；F1；G2；K3；L5。
- **证据：** 实际页面和路由清单确认：教师仅显示 messages 的 JSON；附件返回值只有文件元数据，两个 API 都没有附件内容读取路由。文本附件正文直到 materialize_provider_payload 才被加入模型输入。

**问题：** 没有图片预览、代码全文/行号或下载原件；Filter 没有 file_handler 属性且 bootstrap 没有安装它，Pipe 不处理 __files__。原生上传不强制 process=false。学生页面要求非空文字且一次只能选一个文件，纯图/纯文件提问不可提交。

**影响：** 教师批准的界面内容不能代表实际送模内容，尤其无法审查 Python 文件；计划要求的原生文件、混合附件和附件独立提问尚未完成。

**如何验证/复现：** 上传 .py、图片及混合附件后，从教师页面尝试查看实际字节；对比显示内容与模拟上游 payload；正常 Open WebUI 上传及 process=true 也应覆盖。

**建议修复：** 接通经过所有权校验的不可变附件内容/预览 API，在批准前展示实际送模版本；按准确版本验证 file_handler 与原生上传适配。支持无文字附件提问及最多五份文件。

<a id="H15"></a>

### H15 · High · 有效历史、课堂系统提示词和会话分支没有权威重建

- **位置：** [classroom/app/classroom_service/canonical.py:61](E:/codex-work/sub2api/classroom/app/classroom_service/canonical.py:61)；[classroom/app/classroom_service/service.py:252](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:252)；[classroom/app/openwebui_bridge/native_routes.py:103](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:103)；[classroom/web/student/index.html:18](E:/codex-work/sub2api/classroom/web/student/index.html:18)。
- **关联计划：** B/H10；C3；D5、D8；G1、G2；H2；K3。
- **证据：** 代码确认；同 operation、同 payload 但 chat_id/parent_request_id 不同的提交已复现返回旧请求，未返回冲突。

**问题：** 服务直接采用浏览器给出的全部 messages，包括 system/assistant 历史；parent_request_id 只存储，不校验归属或用于重建。单独传入的聊天/分支/消息关联未进入 digest。自建学生页面每次只发送当前问题，没有完整会话体验；没有服务端课堂提示词配置。

**影响：** 追问无法保证使用教师改写后的有效问题与已归档回答；可混用分支/关联，导出与恢复失真。当前教师看到完整 messages JSON 并不等于实现了不可篡改历史，也不应把这一点误报成所有历史都暗中绕过审批。

**如何验证/复现：** 先修改后批准一问并完成，再通过正常追问提交原文历史或伪造 assistant 内容；比较有效快照。另对同键更换 chat/parent/message 标识应产生受控冲突。

**建议修复：** 按可信聊天/分支关系重建有效历史与课堂提示词，校验所有权，将完整关联、配置和附件哈希纳入规范化摘要；学生只提供本次内容与允许参数。

<a id="H16"></a>

### H16 · High · 教师导出漏掉原生旧聊天，不能兑现全班对话永久留存

- **位置：** [classroom/app/classroom_service/archive.py:41](E:/codex-work/sub2api/classroom/app/classroom_service/archive.py:41)；[classroom/app/openwebui_bridge/native_routes.py:195](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:195)；[classroom/app/classroom_service/database.py:236](E:/codex-work/sub2api/classroom/app/classroom_service/database.py:236)。
- **关联计划：** R12；D9；E3；F3；J3；K4；L5、L7。
- **证据：** 代码确认：导出唯一来源是 classroom review_requests；没有原生 Chats API、legacy 导入器或会话组合查询。迁移脚本只初始化自有表。

**问题：** 没有 classroom request_id 的原生聊天全部遗漏；旧审批和附件也未迁移。导出只有请求粒度，没有完成计划中的原生会话/分支/来源去重。新生成还没有形成正常 Open WebUI 聊天持久化闭环。 导出还缺名册名/登录标识快照、日期过滤和每个文件的校验哈希；虽然有按文件名下载路由，但没有持久导出任务、进度及重放机制。分页读取后仍把全部请求累积进内存。

**影响：** 教师无法导出用户要求的一直保留的完整学生对话。改造前已有聊天不会自动消失，但不能把“仍在旧数据库”算作新版导出完成。

**如何验证/复现：** 准备一个仅存在于原生数据库的学生聊天、一个新课堂请求，导出该学生并按原生管理员 API 对账。

**建议修复：** 复用原生管理员分页 API 读取旧聊天，增加 legacy/provenance 和会话关联，再与课堂不可变归档组合导出；测试学生删改原生聊天后的永久留存。 补充持久导出任务、稳定身份/日期范围、逐文件 SHA256 清单和有界流式输出。

<a id="H17"></a>

### H17 · High · 备份只包含课堂库，缺少账号库、原生聊天和上传文件

- **位置：** [classroom/app/classroom_service/backup.py:23](E:/codex-work/sub2api/classroom/app/classroom_service/backup.py:23)；[classroom/scripts/Backup.ps1:14](E:/codex-work/sub2api/classroom/scripts/Backup.ps1:14)。
- **关联计划：** I3；J1、J4；K5；总验收第 12 项。
- **证据：** 临时数据根中放入模拟 webui.db 后执行实际 backup，ZIP 只有 classroom.db、blobs（若有）和 manifest，原生库不在其中。

**问题：** 缺少 Open WebUI DB、原生 uploads、必要非秘密配置和共同维护屏障；没有校验数据库与附件引用是否属于同一完整备份点。默认输出还是固定文件名，写 ZIP 也没有原子发布。

**影响：** 磁盘故障或换机后无法从这份“备份”恢复登录账号和完整对话；备份失败还可能覆盖上一份同名备份。

**如何验证/复现：** 从已备份目录恢复到新目录，只提供备份 ZIP，核验登录、旧聊天、原生附件、课堂问题和额度；不能借用仍存在的原安装来补全。

**建议修复：** 按计划建立覆盖两个库、已引用文件及非秘密配置的联合备份，维护暂停/一致性屏障、Backup API、引用校验及原子发布；每天启动备份与人工备份使用同一流程。

<a id="H18"></a>

### H18 · High · 恢复在校验之前覆写目标文件，损坏备份会破坏已有数据

- **位置：** [classroom/app/classroom_service/backup.py:55](E:/codex-work/sub2api/classroom/app/classroom_service/backup.py:55)；[classroom/scripts/Restore.ps1:13](E:/codex-work/sub2api/classroom/scripts/Restore.ps1:13)。
- **关联计划：** I3；J4；K5；总验收第 12 项。
- **证据：** 已在临时目录复现：目标 classroom.db 原有唯一副本，恢复一个哈希不匹配的 ZIP，函数抛 ValueError 后原数据已被替换。

**问题：** 允许非空目标目录；直接 path.open('wb') 后才验证哈希。没有先完成格式、版本、所有文件、SQLite 完整性及引用校验。

**影响：** 恢复失败可能毁掉本来完好的唯一数据，属于实际数据丢失缺陷。

**如何验证/复现：** 仅在临时目录放置已知字节的旧库文件，使用错误 manifest 哈希的测试 ZIP 恢复；验证失败后旧文件应逐字节保持不变。

**建议修复：** 默认拒绝非空目标，在全新暂存目录解包并验证全部内容、版本及数据库完整性，再通过明确切换发布；任何失败都保留原目录和原数据。

<a id="H19"></a>

### H19 · High · 含空格或中文空格的路径会被 Start-Process 参数拆开

- **位置：** [classroom/scripts/Start.ps1:47](E:/codex-work/sub2api/classroom/scripts/Start.ps1:47)；[classroom/scripts/Start.ps1:61](E:/codex-work/sub2api/classroom/scripts/Start.ps1:61)。
- **关联计划：** I1；K5；L8；总验收第 11 项。
- **证据：** 用相同 Start-Process -ArgumentList 数组方式启动一个无副作用的 Python 打印脚本，脚本位于“中文 path”目录，实际退出码为 2，错误显示脚本路径在空格处被截断。

**问题：** PowerShell 将 ArgumentList 数组组合为命令行，没有为脚本和 --db/--data-root 路径正确引用。开发机器的无空格路径没有触发。

**影响：** 用户按计划解压到常见含空格目录或设置这类 DataRoot 时无法启动。

**如何验证/复现：** 在临时目录采用同一参数构造方式运行仅打印 argv 的脚本，检查接收参数与原值完全一致；之后再做完整便携启动测试。

**建议修复：** 使用符合 Windows 命令行规则的参数引用或不会丢失边界的启动方式；分别验证解释器、脚本和数据路径含中文、空格以及换盘。

<a id="H20"></a>

### H20 · High · 最终发行包和安全打包流程没有完成

- **位置：** [classroom/scripts/Build-Package.ps1:2](E:/codex-work/sub2api/classroom/scripts/Build-Package.ps1:2)；[classroom/scripts/Build-Package.ps1:9](E:/codex-work/sub2api/classroom/scripts/Build-Package.ps1:9)；[classroom/requirements-runtime.lock:1](E:/codex-work/sub2api/classroom/requirements-runtime.lock:1)；[classroom/IMPLEMENTATION_STATUS.md:27](E:/codex-work/sub2api/classroom/IMPLEMENTATION_STATUS.md:27)。
- **关联计划：** H1；I1；J；L8、L9；交付物第 1—4 项。
- **证据：** 目录核对：只有旧 v1.0.0 ZIP，没有新完整发行包。当前 Build-Package 生成 source ZIP，不包含便携运行时；原包页面错位、旧说明和旧审核组件仍存在。

**问题：** 默认输出位于被递归复制的 classroom/release 内，源/目标形成包含关系，存在自复制失败/递归风险（未执行该危险建包路径）。脚本只排除 Python 缓存，不排除运行 data/logs/backups/凭据，却硬写 contains_live_data=false。依赖锁无安装包哈希，未覆盖完整组件；原生和旧课堂数据迁移/回滚没有实现。

**影响：** 无法交付用户要求的解压即用新包；执行过默认启动后再打源码包可能夹带真实数据。人工设置 verified 不能替代迁移证据。

**如何验证/复现：** 在干净、无真实数据的 staging 目录建包，先检查源/输出不互相包含；用合成敏感标记验证 data/logs 不入包；换机解压及迁移副本验收。

**建议修复：** 使用源目录外的干净 staging 和正向文件清单；生成完整 Windows 包、SHA256、组件清单、正确入口/页面布局及同步指南。完成 J 节迁移和恢复验证后才生成可发布包。

<a id="H21"></a>

### H21 · High · 学生 LAN HTTP 页面依赖仅限安全上下文的 randomUUID

- **位置：** [classroom/web/student/index.html:18](E:/codex-work/sub2api/classroom/web/student/index.html:18)；[classroom/web/teacher/index.html:22](E:/codex-work/sub2api/classroom/web/teacher/index.html:22)。
- **关联计划：** C3；G1；I1；K4、K5。
- **证据：** 代码与 Web 标准确认，未做真实浏览器实网复现。W3C Web Cryptography API 的 Crypto 接口把 randomUUID 标为 SecureContext；计划默认是 http://教师局域网IP:3000。localhost 测试不能覆盖此条件。

**问题：** 页面无兼容分支直接调用 crypto.randomUUID。普通 LAN HTTP 不属于默认可信 localhost/HTTPS 上下文；此外操作 UUID 也没有持久化供失败重试或刷新沿用。

**影响：** 标准浏览器的默认 LAN 部署可能在提交/调额时抛出 TypeError；手工再次点击又会使用新的操作键，不能保证跨刷新重传。

**如何验证/复现：** 在实际学生机器上通过教师 LAN IP 的 HTTP 地址检查 window.isSecureContext 和 typeof crypto.randomUUID，完成提交与重试；不要用 localhost 代替。

**建议修复：** 为计划允许的 HTTP 场景提供安全随机操作 ID 的兼容实现或服务端分配，并在当前操作中持久化；HTTPS 可作为另行部署选项，不应把强制改用 HTTPS 当成无说明的范围变更。

标准依据：[W3C Web Cryptography API — Crypto interface](https://w3c.github.io/webcrypto/#crypto-interface) 将 randomUUID 标记为 SecureContext。此项是标准与默认部署条件的推断；真实学生机器测试尚未执行。

## 5. Medium 与 Low 缺陷

<a id="M01"></a>

### M01 · Medium · 图片校验只看头部，合法 WebP 反而可能被拒绝

- **位置：** [classroom/app/classroom_service/attachments.py:41](E:/codex-work/sub2api/classroom/app/classroom_service/attachments.py:41)；[classroom/app/classroom_service/attachments.py:77](E:/codex-work/sub2api/classroom/app/classroom_service/attachments.py:77)；[classroom/app/classroom_service/attachments.py:88](E:/codex-work/sub2api/classroom/app/classroom_service/attachments.py:88)。
- **关联计划：** G2；K3；L5。
- **证据：** 已复现：24 字节假 PNG 被接收但 Pillow 无法解码；Pillow 生成的有效无损 VP8L WebP 被拒绝。

**问题：** 没有完整解码/verify 或安全预览；WebP 只识别 VP8X，未支持常见 VP8/VP8L。头部尺寸不能证明整个文件有效。

**影响：** 教师预览或提供商处理会在审批后失败；常见学生图片无法上传，声明支持的格式与实际不一致。

**如何验证/复现：** 使用截断 PNG/JPEG、有效 VP8/VP8L/VP8X、尺寸炸弹和扩展名伪装样本，分别测试入库、预览和实际送模字节。

**建议修复：** 复用已打包 Pillow 的受限解码、尺寸检查、验证与规范化预览；限制解码成本，保留原件和送模版本哈希。

<a id="M02"></a>

### M02 · Medium · 外部请求缺少统一模式、Content-Type 和 Cookie 写请求来源校验

- **位置：** [classroom/app/openwebui_bridge/native_routes.py:95](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:95)；[classroom/app/openwebui_bridge/native_routes.py:144](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:144)；[classroom/app/classroom_service/api.py:104](E:/codex-work/sub2api/classroom/app/classroom_service/api.py:104)。
- **关联计划：** B/M02；E1；H3；K2。
- **证据：** 代码确认：多数端点直接 await request.json() 然后 body.get；没有统一 object/type/未知字段校验，也没有 CSRF/Origin 校验。原生只提供 CORS，不能替代 Cookie 写操作授权来源检查。

**问题：** 数组、null、错误类型或非 JSON Content-Type 可能产生 500/意外接受；Cookie 会话下只要浏览器带上凭据，恶意同站不同源的写请求缺少额外校验。这里确认的是保护缺失，不宣称已经完成跨浏览器远程 CSRF 利用。

**影响：** API 错误不稳定、难以恢复；写入入口存在来源边界缺口。

**如何验证/复现：** 在隔离接口发送 []、null、text/plain JSON、未知控制字段，以及带有效测试 Cookie 的不允许 Origin，确认返回受控 4xx 且没有状态变化。

**建议修复：** 使用统一严格请求模型和大小限制；写操作校验 Cookie 会话 CSRF/Origin，明确 bearer 跨源策略；统一稳定错误码，不向客户端暴露原生异常详情。

<a id="M03"></a>

### M03 · Medium · 资源和模型能力限制未覆盖真实请求生命周期

- **位置：** [classroom/app/openwebui_bridge/native_routes.py:121](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:121)；[classroom/app/classroom_service/canonical.py:21](E:/codex-work/sub2api/classroom/app/classroom_service/canonical.py:21)；[classroom/app/classroom_service/attachments.py:108](E:/codex-work/sub2api/classroom/app/classroom_service/attachments.py:108)；[classroom/app/classroom_service/worker.py:51](E:/codex-work/sub2api/classroom/app/classroom_service/worker.py:51)；[classroom/app/classroom_service/service.py:637](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:637)。
- **关联计划：** 默认值；C5；D6、D8；G2；I3；K3、K5。
- **证据：** 代码确认：附件在读取全部 JSON/base64 后才检查字节大小；内容 part 数量/总上下文没有统一上限；HttpUpstream 只有一个 socket timeout。未发现速率限制、磁盘阈值、临时上传清理或图像能力校验。

**问题：** 模型上下文超限和不支持图像直到上游才发现；没有 60 秒首正文/300 秒总时限、输出总量和有界事件合并。未提交附件默认 permanent，永不清理。每个 delta 都开事务并重写完整 output_text。

**影响：** 学生可制造大量无关上传或巨大输入；长流/磁盘不足可能拖慢全班并增加存储压力。固定单文件限制不能替代总资源边界。

**如何验证/复现：** 在受控模拟下测试大 JSON、多 part、连续小 chunk、超上下文、无图像能力模型、低磁盘和七天未提交上传；不得向真实上游做压力测试。

**建议修复：** 在边界限制请求体/速率/附件总量；入队前验证模型能力和上下文预算；加入首输出/总时限、输出上限、批量持久化、临时对象引用管理和低磁盘暂停。

<a id="M04"></a>

### M04 · Medium · 关键数据库约束和账目对账缺失

- **位置：** [classroom/app/classroom_service/database.py:71](E:/codex-work/sub2api/classroom/app/classroom_service/database.py:71)；[classroom/app/classroom_service/database.py:118](E:/codex-work/sub2api/classroom/app/classroom_service/database.py:118)；[classroom/app/classroom_service/database.py:269](E:/codex-work/sub2api/classroom/app/classroom_service/database.py:269)；[classroom/app/classroom_service/service.py:637](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:637)。
- **关联计划：** D4、D5、D7、D10；K1、K2。
- **证据：** DDL 核对：有唯一终态结算索引、唯一 attempt；没有 user_id+operation_id 唯一约束、每人活动请求部分唯一索引、总额度非负/预留上限约束。ready_report 不核对 ledger。

**问题：** 一致性主要依赖特定服务函数的 BEGIN IMMEDIATE 与 Python 检查；缺少计划要求的数据库最后防线。SQLite quick_check 只能检查结构，不能证明业务账目正确。

**影响：** 后续维护、迁移或新写入路径更容易引入重复活动/不一致账目；错误账目不会阻止派发。本轮正常并发测试通过，未发现现有 submit 路径已经因此重复扣次。

**如何验证/复现：** 在临时库检查索引/约束，并注入 ledger 与日桶差异；系统应报告维护状态，而不继续 ready。

**建议修复：** 通过版本化迁移补齐约束，先处理现有数据冲突；实现 ledger 聚合对账与启动/恢复校验，发现差异时暂停执行并提供诊断。

<a id="M05"></a>

### M05 · Medium · VerifyOnly 会写数据库，校验失败前也可能执行 DDL

- **位置：** [classroom/app/classroom_service/migrate.py:13](E:/codex-work/sub2api/classroom/app/classroom_service/migrate.py:13)；[classroom/app/classroom_service/database.py:317](E:/codex-work/sub2api/classroom/app/classroom_service/database.py:317)；[classroom/scripts/Migrate.ps1:16](E:/codex-work/sub2api/classroom/scripts/Migrate.ps1:16)。
- **关联计划：** D1；I2；J1、J2；K5。
- **证据：** 复现：对不存在的路径执行 migrate(..., verify_only=True)，创建了 176128 字节数据库。initialize 先执行 SCHEMA，再比较 checksum。

**问题：** verify_only 只是报告字段，没有影响打开模式或执行流程。校验版本/哈希之前就可能创建表、索引和迁移记录。

**影响：** 教师/执行 AI 以为进行只读检查时实际修改数据；坏基线可能被部分改变，妨碍可靠迁移分析。

**如何验证/复现：** 对不存在库和故意缺少一个对象的临时库执行 VerifyOnly，比较文件存在性、哈希及 sqlite_master 前后差异。

**建议修复：** 把只读验证与迁移彻底分开；VerifyOnly 使用 mode=ro，先校验版本/哈希/结构，不运行初始化。真实迁移先校验前置版本，再在受控事务中执行。

<a id="M06"></a>

### M06 · Medium · 时区探测失败会静默退回 UTC，系统时钟回退没有保护

- **位置：** [classroom/app/classroom_service/clock.py:27](E:/codex-work/sub2api/classroom/app/classroom_service/clock.py:27)；[classroom/app/classroom_service/service.py:35](E:/codex-work/sub2api/classroom/app/classroom_service/service.py:35)。
- **关联计划：** R02；C6；K1。
- **证据：** 代码确认：tzlocal 异常时返回环境变量或 UTC；没有持久化的业务时间回退检测或暂停逻辑。

**问题：** 开发便利的 fallback 被生产路径复用，违背“教师机时区不可识别时暂停，而不是默默建桶”的规则。

**影响：** 异常机器配置下，重置日界/过期时间可能错误；时钟回退可能创建非预期日期桶。

**如何验证/复现：** 模拟 tzlocal 报错、缺失 tzdata、Windows 时区变化和时钟倒退，验证错误、日桶复用及维护状态。

**建议修复：** 生产与测试时钟策略分离；无法可靠识别时区或检测到异常回退时停止新预留/派发，保留历史日桶并提供恢复步骤。

<a id="M07"></a>

### M07 · Medium · 启动/停止和自定义目录、端口仍有不完整状态

- **位置：** [classroom/scripts/Start.ps1:29](E:/codex-work/sub2api/classroom/scripts/Start.ps1:29)；[classroom/scripts/Start.ps1:43](E:/codex-work/sub2api/classroom/scripts/Start.ps1:43)；[classroom/scripts/Start.ps1:59](E:/codex-work/sub2api/classroom/scripts/Start.ps1:59)；[classroom/scripts/Stop.ps1:13](E:/codex-work/sub2api/classroom/scripts/Stop.ps1:13)；[classroom/app/openwebui_bridge/native_routes.py:237](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:237)。
- **关联计划：** B/M04；I1、I2；K5；L7。
- **证据：** 代码确认：Start 只要旧 service PID 匹配就退出，不检查 WebUI；也接受任何 ready health。Stop 不做业务暂停/排空，失败后仍删除 PID 文件。DataRoot 只控制课堂库，原生库固定在 bundle/data/openwebui。

**问题：** 没有单实例排他锁、命令行/实例身份校验和单服务恢复。自定义 WebPort 不传到改密/重置的默认 3000 内部地址。每日启动仍重新索要教师密码并 bootstrap。防火墙规则没有 LocalSubnet 限制，且新版教师说明调用了不存在的 -Action 参数。

**影响：** 半启动无法自愈、可能误认服务或失去停止记录；换目录/端口后账号操作失败，日常便携使用依赖人工修复。

**如何验证/复现：** 只保留服务进程而关闭 WebUI、占用端口、缺失 PID 时间字段、使用自定义 DataRoot/WebPort，逐一验证 Start/Stop/Status 与改密；用 -WhatIf 核对防火墙脚本参数。

**建议修复：** 统一安装配置与两个数据目录/内部地址；严格实例锁和所有权检查，按组件恢复；正常关闭前暂停/排空并核验退出。一次性初始化与日常启动分开，修正防火墙作用域和说明。

<a id="M08"></a>

### M08 · Medium · 教师和学生页面缺少多项已承诺的操作与恢复流程

- **位置：** [classroom/web/teacher/index.html:11](E:/codex-work/sub2api/classroom/web/teacher/index.html:11)；[classroom/web/teacher/index.html:20](E:/codex-work/sub2api/classroom/web/teacher/index.html:20)；[classroom/web/student/index.html:16](E:/codex-work/sub2api/classroom/web/student/index.html:16)；[classroom/app/openwebui_bridge/native_routes.py:86](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:86)。
- **关联计划：** R08、R09、R12；E2、E3；F1—F3；G1；K4；L6。
- **证据：** 页面/路由逐项核对：无修改后批准 UI、批量审批、全选全班、自定义调额、单人暂停、课堂暂停/教师停止按钮、历史筛选、单人/多人导出选择；/me 只返回 pending 活动请求。

**问题：** 刷新后的 approved_queued/generating 无法自动恢复；操作 ID/活动请求未持久化。没有原生首次登录跳转或完整历史页，拒绝/修改说明和额度更新不完整。三秒全量重画教师名册会重置勾选，提交保护不足。

**影响：** 用户确认的单独/批量管理与日常教学流程并未完成；部分后端函数存在但教师没有可用入口。

**如何验证/复现：** 按原计划 F/G 的教师、学生任务清单逐项点击执行，并在待审、排队、生成三种状态刷新；选择学生后等待一次自动刷新再操作。

**建议修复：** 补齐必要界面与对应授权 API，保留选择/预览/操作状态，使用稳定分页和错误恢复；在准确 Open WebUI 前端中验证首次改密、提交、停止与恢复完整路径。

<a id="L01"></a>

### L01 · Low · 说明书和完成声明与实际行为不一致

- **位置：** [classroom/TEACHER_GUIDE_CN.md:27](E:/codex-work/sub2api/classroom/TEACHER_GUIDE_CN.md:27)；[classroom/IMPLEMENTATION_STATUS.md:6](E:/codex-work/sub2api/classroom/IMPLEMENTATION_STATUS.md:6)；[classroom/baseline/README.md:3](E:/codex-work/sub2api/classroom/baseline/README.md:3)；[dist/openwebui-classroom-review-windows-x64/教师使用说明.md:9](E:/codex-work/sub2api/dist/openwebui-classroom-review-windows-x64/教师使用说明.md:9)。
- **关联计划：** I1；L9；交付物第 4—7 项。
- **证据：** 文档对照确认。新指南描述附件展开、修改后批准、自定义/全班操作和部分导入恢复，代码尚无这些流程；原发行说明仍指向密码 JSON、8790 老页面和原生提供商设置。

**问题：** “核心完成”把未运行的适配/辅助函数当成已接通功能；baseline README 声称有源码快照但只见 manifest。阶段 8/9 未完成的披露是正确的，但不足以覆盖前面阶段的缺陷。

**影响：** 教师或下一位 AI 可能依据文档错误开放学生访问、忽略数据/恢复缺口。

**如何验证/复现：** 逐项照指南操作并与真实 API、目录和测试报告核对；报告必须列出完整启动/原生集成未通过，而不仅是真实模型与迁移未测。

**建议修复：** 整改后重新生成与最终发行包一致的说明；分开列出已实现、已验证、模拟验证、未完成，保留失败证据，不用静态兼容清单代替实测。

<a id="L02"></a>

### L02 · Low · 存在未接通及重复的安全/账号实现，容易继续修错路径

- **位置：** [classroom/app/openwebui_bridge/integration.py:34](E:/codex-work/sub2api/classroom/app/openwebui_bridge/integration.py:34)；[classroom/app/openwebui_bridge/native_api.py:11](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_api.py:11)；[classroom/app/classroom_service/api.py:56](E:/codex-work/sub2api/classroom/app/classroom_service/api.py:56)；[classroom/app/openwebui_bridge/native_routes.py:20](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py:20)。
- **关联计划：** H1、H2；L1、L3；实现一致性要求。
- **证据：** 调用者核对：ClassroomIntegration、NativeOpenWebUIAdapter 没有运行路径；两份外部 API 的账号、会话和导出能力不同，测试只覆盖其中一份。

**问题：** 安全检查散落在自签 session、原生懒登记、纯 RouteGuard 和实际 middleware 中。部分表字段/方法只是预留或无调用者，却被文档作为完成证据。

**影响：** 后续只修测试经过的实现仍可能漏掉真正上线的入口；重复代码增加权限与错误处理漂移。

**如何验证/复现：** 从 launcher 追踪所有 endpoint 到实际 helper，并比较两份 API 的认证、账号和调额路径；检查未引用符号。

**建议修复：** 在保留已验证核心的前提下收敛到明确的运行入口和版本适配层；删除或明确标记非生产测试辅助代码，为真实入口补契约测试。

## 6. 缺失或不完整的需求

下面按用户可感知的交付归纳；详细到字段、端点和用例的状态见 [逐项检查表](E:/codex-work/sub2api/CLASSROOM_AI_AUDIT_CHECKLIST.md)。

| 要求 | 已有成果 | 尚缺或错误 |
|---|---|---|
| 唯一受管模型出口 | Pipe、部分拒绝前缀、Service/Worker | 真实模型/操作 ID 映射、全路由能力清单、凭据迁移、独立调度器、教师测试、真实 readiness。 |
| 原生账号和首次改密 | 标准 CSV、独立名册、epoch/指纹表、原生 API 调用 | 成功登录 hook、禁止旧 JWT 懒登记、REST/WS 统一安全检查、12 小时时限、pending 过渡、重置先封锁、原生 UI 同等处理、导入恢复/已有账号接管。 |
| 计数和失败语义 | 预留/正式使用分离、拒绝收费、单 claim/结算 | SSE 错误/截断判定、已交付正文定义、真实上游停止、自动重启/跨日恢复、派发授权复查、HTTP 调额幂等/日期/版本。 |
| 学生聊天 | 独立简易输入页、状态查询、事件表 | 原生聊天体验与分支、刷新恢复排队/生成、操作键持久化、初始登录跳转、LAN HTTP 支持、原文/教师有效改写展示。 |
| 教师日常管理 | 单条批准/拒绝、选中学生 +/-1、导入/重置、全班导出按钮 | 修改后批准、图片/代码全文、批量审批、全班全选/自定义调整、单人暂停、课堂暂停/教师停止按钮、历史筛选和清楚的错误恢复。后端已有教师 stop、课堂 state、model-policy 与导出下载，不应误记成全部不存在。 |
| 附件与上下文 | 本地不可变 blob、实际哈希、文本解码、部分多模态快照 | 原生 process=false 强制、Filter file_handler/可信文件关联、纯文件提问、真实解码/预览、内容下载、有效历史重建、模型上下文/图像能力预检。 |
| 永久历史和导出 | 新课堂请求/输出/附件局部 ZIP | 原生旧聊天和旧审批迁移、会话/来源合并、名册身份快照、日期/单人多人范围、完整清单哈希、持久导出任务与进度、有界流式导出。 |
| 便携运行和升级 | 新增若干脚本、局部健康检查/迁移工具 | 原包可运行集成、空格路径、统一配置/DataRoot、实例锁、单服务恢复、全备/非破坏恢复、原生迁移/受保护回滚、最终全量 ZIP/锁/校验/新指南。 |
| 长期资源边界 | 单文件/每请求部分限制 | 入站请求体与速率限制、首输出/总生成/响应量限制、磁盘容量显示及低空间暂停、未提交上传清理、账目与文件引用对账。 |

缺失项目不是单纯“后续增强”：它们多数已是原计划明确要求。尤其不能把迁移、旧聊天、原生认证和真实提供商唯一出口列为不影响验收的可选工作。

## 7. 回归风险

| 场景 | 证据等级 | 可能回归 / 已确认结果 |
|---|---|---|
| 替换旧 launcher 和 scripts 后直接日常启动 | 代码及隔离运行证实 | 原先可启动的 WebUI 入口出现模块导入/空格路径失败；当前源码在原生迁移 marker 未验证时拒启是合理保护，不能将其与后续导入错误混为一谈。 |
| 修复挂载后开放课堂聊天 | 真实准确版本调用链确认 | 同步 Pipe 等待会阻塞同进程教师审批/其他请求；修挂载本身不会解决执行问题。 |
| 为恢复聊天而放宽 middleware | 已复现旁路，修复时必须回归 | 现有教师/学生都被挡；粗暴解除拦截会进一步开放原生提供商和副任务。应按角色/能力与唯一出口联动修复。 |
| 教师重置后认为旧密码/会话失效 | 原生桥接探针证实 | 未登记旧 JWT 可重新登记，原生管理重置不更新课堂安全状态；学生首次改密可被错误标记完成。 |
| 网络抖动、空流、主动停止 | 实际解析器/阻塞模拟证实 | 误扣次数、后台调用继续、并发数超过配置；不能只看状态表已经 final。 |
| 服务重启或午夜不再有新提交 | 文件库/时钟探针证实 | 遗留预留和昨日待审不清理，ready 仍可为真，阻塞下一次正常提问。 |
| 教师在批准后暂停学生/移除模型 | 真实核心调用顺序复现 | 排队授权没有被重新验证，旧模型仍可发送。 |
| 学生打开旧聊天继续追问 | 代码确认 | 系统未从教师有效改写重建上下文，当前简易页也不具备完整会话关联；旧对话导出漏项。 |
| 换机/磁盘故障后依赖 Backup | 临时数据实证 | 缺账号库、旧聊天和上传，不能完整恢复；损坏备份会覆盖目标旧数据后失败。 |
| 执行默认 Build-Package | 条件风险，未执行危险路径 | 源/目标包含关系及未排除 data/logs/凭据可能造成建包失败或泄漏；manifest 的 false 声明不能代替扫描。 |
| 正常学生 LAN HTTP 浏览器 | 标准支持的条件问题 | crypto.randomUUID 可能不可用，localhost 验证无法覆盖；需实际 LAN 场景复验。 |
| 原 Go/Vue Sub2API | 本轮未见相关改动 | 没有因本次课堂变更确认 Go/Vue 回归；不为该独立产品虚构缺陷或扩大重写范围。 |

## 8. 测试覆盖缺口

30 个绿色测试主要验证直接业务函数和模拟依赖。具体盲点包括：

- [classroom/tests/test_security_and_guard.py](E:/codex-work/sub2api/classroom/tests/test_security_and_guard.py) 的会话撤销走自签 `sessions.issue/validate`，实际原生路由走 `register_native_token`；两个路径结果不同。纯 `RouteGuard` 通过不能证明运行中的 `ClassroomRouteGuardMiddleware` 具有同样的角色/模型判断。
- [classroom/tests/test_api.py](E:/codex-work/sub2api/classroom/tests/test_api.py) 创建独立 `create_app`，没有保留准确 Open WebUI 的根 SPA mount 顺序，因此无法发现课堂 API 被遮挡；另有原生路由安装探针也不能替代完整 launcher。
- [classroom/tests/test_recovery.py](E:/codex-work/sub2api/classroom/tests/test_recovery.py) 直接调用 `reconcile_leases`，不证明启动/后台会调用它；模型变更测试只断言退回 pending，没有再次批准并检查真正派发模型。
- 假提供商直接返回字符串列表或抛异常，绕过真实 HttpUpstream 的 SSE 结束/错误解析。停止测试把数据库写入正文当作可见，不验证有效订阅交付，也不统计真实存活 HTTP 调用。
- [classroom/tests/test_backup.py](E:/codex-work/sub2api/classroom/tests/test_backup.py) 的局部课堂库往返不能发现原生库缺失；缺坏备份恢复后旧文件必须不变的断言。
- 通过手工 sys.path、独立 FastAPI 或 `-NoOpenWebUI` 启动成功，不能证明原始 `python311._pth`、完整 WebUI 和最终发行目录可用。

必须补齐的测试应围绕实际行为，而不是再给已有 getter/字段写重复测试：

| 优先级 | 测试组 | 必须观测的断言 |
|---|---|---|
| P0 | 准确版本完整启动/挂载 | 原包解释器、原 ._pth、最终目录，实际学生/教师 HTML 和 JSON 内容类型；正常聊天模型 ID、可信操作关联、教师审批可响应。 |
| P0 | 全模型出口与能力枚举 | 根据实际路由表覆盖 messages/embeddings/files/process/tasks/audio/images/tools 等；未授权实际上游调用数为 0；删除 Pipe/修改配置/未知版本时关闭学生能力。 |
| P0 | 原生会话全生命周期 | 两个真实原生测试会话，包含从未登记的旧 JWT；初改、正常改密、教师两种重置界面、退出、12 小时、角色变化、REST/WS、无 Redis。 |
| P1 | 提交到完成的真实异步流程 | 教师批准前 0 调用、批准后 1 调用；等待审批时其他学生与教师 API 可响应；提交/刷新/续订不另建调用。 |
| P1 | 提供商流协议 | 有效完成、finish_reason/DONE、SSE error、空 200、错误格式、partial 后 EOF、首输出超时、总超时；故障保留部分输出、零扣、无自动重发。 |
| P1 | 停止与并发竞争 | 无正文/持久化未交付/已交付、claim 竞争、阻塞 read、学生/教师停止、网络断开；真实存活调用数与并发槽一致。 |
| P1 | 生命周期和日界 | 用进程启动/后台任务/正常查询触发恢复，不直接调用辅助函数；午夜决定、生成跨日、未知派发、时区变更/DST/时钟回退、ledger 对账。 |
| P1 | 账号跨库失败 | 原生建号后/保存 ID 前/enrollment 前后/返回结果前失败；pending 安全状态、同批次重放、重新提供源文件恢复、全无效行结果、原生 200 false。 |
| P1 | 教师实际调额 | 页面头与 JSON 契约，重传相同 key、同 key 异体、预览后并发修改、午夜提交旧预览；任何一人失败整批不变。 |
| P1 | 附件/有效上下文 | 原生实际上传不调用模型，教师看到的规范化内容/hash 等于发送 payload；纯文件/混合、越权、删除/替换、有效 WebP/坏图、模型图像/上下文预算、教师改写后的追问。 |
| P1 | 联合备份恢复/迁移 | 仅靠备份在新目录恢复账号、旧聊天、全部引用 blob、额度和历史；坏备份保持原数据不变；官方迁移基线/旧记录来源/安全回滚逐项对账。 |
| P2 | 真实教师/学生 UI | 计划 F/G 的全部操作、勾选不被轮询清除、错误/取消/恢复、LAN HTTP、30 浏览器和 p95；真实模型只做获授权的必要功能验证。 |
| P2 | 资源与包 | 大请求、速率、低磁盘、写失败、SQLite busy、长期小 delta；干净 Windows/中文空格/换盘/端口冲突/半启动；ZIP 正向清单和秘密扫描。 |

已测/未测应分别记录运行环境、版本、输入、预期、实际状态和出口次数。安全测试的终点是出口调用数，恢复测试的终点是正常运行生命周期，备份测试的终点是脱离原安装仍能恢复。

## 9. 可接受的设计差异

| 实现选择 | 判断 | 条件/边界 |
|---|---|---|
| 单班使用 SQLite、本地文件，不额外部署 Redis/PostgreSQL | 可接受，符合计划 | 仍要完成无 Redis 原生会话撤销与单实例/恢复，不能用架构简单为理由省略。 |
| 将请求/设置逻辑合并到 service.py，将 exports 合并到 archive.py | 物理文件合并本身可接受 | 原计划允许逻辑模型合并；以功能、约束和调用路径验收，不要求机械创建所有示例文件。重复外部 API/安全实现的漂移另见 L02。 |
| 自有初版 DDL 存在 Python 字符串中并记录 checksum | 可接受 | 必须修复先 DDL 后校验和 VerifyOnly 写库；未来版本必须有明确迁移，不能只靠 CREATE IF NOT EXISTS。 |
| 额度按首次观察日期惰性建桶 | 可接受且符合计划 | 不需要午夜开机；启动/查询自动过期与异常时钟保护仍必须实现。 |
| 新课堂 blob 独立于原生附件目录 | 可接受且有益 | 能避免原生删除破坏新归档；需要真实文件适配、教师内容查看和联合备份。 |
| 顺序建号而非并发 2—4 | 可接受的更保守选择 | 30 人规模无需为吞吐增加风险；应测完成时间并补跨库安全/恢复。 |
| 用模拟提供商做本轮测试、不对生产施压 | 可接受且符合计划 | 必须覆盖实际 HttpUpstream、原生 API 和完整运行生命周期，不能把模拟的组件测试声明成实网验收。 |
| 迁移基线未证明时拒绝启动 | 正确的保护性选择 | 原实施报告披露阶段 8/9 未完成应保留；手动 verified 字符串不构成迁移证明，也不能将阶段 1—7 的独立缺陷掩盖为“只差迁移”。 |

自建简单聊天页、多个服务实例直接读写同一 DB、仅用 URL 黑名单、把 provider 放回 WebUI、放弃旧聊天，不是已经证明更好的等价替代。它们没有满足原生体验、唯一出口、认证和永久历史要求，不能作为可接受差异通过。

## 10. 原计划本身的问题

本轮没有发现必须推翻核心方案或改写用户 R01—R12 的事实性设计错误。尤其异常中断不扣、已交付回答后的主动停止收费、禁止懒登记旧 JWT、原生文件 process=false、验证后再恢复、准确版本 Stage 1 契约均已明确写入原计划；这些失败应归于实现，不应反过来归咎需求含糊。

计划可以补充以下实施与验收细节，属于规格细化，不能消除当前缺陷：

1. **LAN HTTP 的操作 ID 生成。** 原计划要求 UUID 并允许受控 LAN HTTP，但没有指定兼容安全上下文受限浏览器的生成方式。应明确服务器分配或兼容的安全随机实现，并测试 IP 地址 HTTP；并不意味着用户已经要求强制新加 TLS 部署范围。
2. **两阶段启动自检。** 应把“服务可受理内部管理”和“完整保护链允许学生调用”分开。否则在 WebUI/Pipe 尚未安装时要求完整 ready，容易实现为循环等待或虚假 ready。原计划已要求保护验证后开放学生，具体引导状态/一次性凭据可进一步列成契约。
3. **已交付正文的测试定义。** 原计划已经要求持久化且交付到有效订阅，并规定停止携带最后序号；可再给出丢包、重连、已写未发、已发未确认的固定测试时序。不能把此细节省略解释成允许仅按 output_text 非空收费。
4. **联合备份的写入屏障。** 可明确屏障同时覆盖原生认证/聊天写入、课堂事务和文件发布，并给出 backup_id/引用对账步骤。当前只备份一库、先覆盖后验证明显违反已有 I3，无须等待计划补充才修复。
5. **阶段交付证据格式。** 应要求 Stage 1 提供准确 launcher、实际路由表、安装内容 hash 和零出口断言的自动报告，再接受后续阶段完成声明。原计划已经设了该阶段门槛，此处是防止再用辅助类测试替代集成验收。

这几项不改变需求、不引入多班或服务集群，也不要求重写 Open WebUI。

## 11. 按优先级整改与复验计划

此表是下一轮修改建议；本轮未实施其中任何代码或部署变更。

| 顺序 | 工作包 | 关联问题 | 完成门槛 |
|---|---|---|---|
| P0-1 | 保持学生生成入口关闭，保留原数据；修复恢复的非破坏性边界与全备能力 | C01、H17、H18、H20 | 不靠设置 verified 开放；隔离新目录恢复验证失败时原数据逐字节不变；能完整恢复两个库及引用文件。 |
| P0-2 | 先完成 Stage 1 的真实原生集成 | H01—H05、H19、H21 | 原始便携解释器/最终目录可启动；路由在根 SPA 前；真实模型 ID/稳定操作 ID；异步等待时教师可审批；LAN HTTP 可提交。 |
| P0-3 | 完成唯一执行出口与真实 readiness | C01、H03、H04、H12 | 服务唯一持有上游能力，运行调度器；原生所有非授权出口零调用；配置破坏/未知版本关闭学生；教师保留管理。 |
| P0-4 | 收敛并接通原生认证和账号生命周期 | H06—H08、L02 | 成功登录登记、拒绝旧 JWT 懒登记、REST/WS 全覆盖、先锁定重置、安全 pending 导入、跨重启幂等恢复，必改账号只能改密。 |
| P1-1 | 修复流协议、交付、取消和自动恢复 | H09—H12、M03、M04、M06 | 明确 completed 信号；故障零扣；停止真实取消且并发槽不提前放开；启动/后台恢复自动执行；日桶/ledger 对账。 |
| P1-2 | 打通 HTTP 写入契约和教师操作 | H13、M02、M08 | Header/日期/版本/CSRF/严格 schema 一致；重传不二次调额；所需批量、全班、暂停/停止、错误恢复均可操作。 |
| P1-3 | 完成附件真实审阅及有效会话归档 | H14—H16、M01、M03 | 实际 teacher preview、快照与提供商 payload 字节/hash 一致；原生上传零副调用；追问用教师有效版本；旧聊天可组合导出。 |
| P1-4 | 完成隔离原生迁移、旧数据和受保护回滚 | H16—H18、H20、M05 | 官方 schema/数据转换等价证明或受控迁移；用户 ID/聊天/附件/审批数量和 hash 对账；无追扣；回滚保留新产生历史且不开旧旁路。 |
| P2-1 | 完成运维、资源与正式包 | H19、H20、M03、M07 | 单实例、统一配置、半启动恢复、正确停止/空间阈值；干净 staging、全量依赖/哈希、中文空格/换盘/干净 Windows 通过。 |
| P2-2 | 同步文档并按十二项总验收重跑 | L01、L02 及所有未关闭项目 | 中文指南和最终包一致；每行 PASS 有对应证据；既有 30 测试继续通过，新增准确入口和失败矩阵通过，未测项公开列出。 |

优先保留已经有证据的额度事务、唯一结算、不可变 blob 和标准 CSV 解析。整改应沿原计划逐层接通并复验；仅扩大测试数量、修页面或把未调用的方法改名，都不能关闭本报告的集成缺陷。

## 附录：审计快照定位

以下 SHA256 锁定本轮主要证据文件；行号均已在当前文件中复核。它们不含任何运行凭据或用户数据。后续修复改变文件后，应按符号和新版本重定位，而不是沿用旧行号。

| 文件 | SHA256 |
|---|---|
| [CLASSROOM_AI_IMPLEMENTATION_PLAN.md](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md) | `8F0573C86685A114B8293BDC0FC7A8F584F797DA39FA0EF1AF27BDC4D61E4EA3` |
| [classroom/app/run_openwebui.py](E:/codex-work/sub2api/classroom/app/run_openwebui.py) | `0A68D10350741CC0186D9C90E12DA028A198EF2A0F9CB133E5839E0B35E49D09` |
| [classroom/app/openwebui_bridge/middleware.py](E:/codex-work/sub2api/classroom/app/openwebui_bridge/middleware.py) | `46CC3CFAE09E0092D04F6362C96607EA7797060118F295ED6D911993071F7D96` |
| [classroom/app/openwebui_bridge/native_routes.py](E:/codex-work/sub2api/classroom/app/openwebui_bridge/native_routes.py) | `02CA26A8BE42211BA209AEDEF8E0DFC092A20C811929DDC4E9F2416D6F15E488` |
| [classroom/app/classroom_service/service.py](E:/codex-work/sub2api/classroom/app/classroom_service/service.py) | `C85755BB2835DB0009D0A0F387D4AD63EE9E328430B623A31BAE0A70785FBE34` |
| [classroom/app/classroom_service/worker.py](E:/codex-work/sub2api/classroom/app/classroom_service/worker.py) | `61766DB50D0D6A23BADA480A92D979DFEB7429643855C378B18F872B0B9B6D35` |
| [classroom/app/classroom_service/auth.py](E:/codex-work/sub2api/classroom/app/classroom_service/auth.py) | `1FA95F067C1478375D7312D4DFE44F1A92DDA21F4A6B78BDDC02405BC58BE6D6` |
| [classroom/app/classroom_service/accounts.py](E:/codex-work/sub2api/classroom/app/classroom_service/accounts.py) | `88BA00897208286AD1790602E1C2BE5EF28C18EEFF88B95231C5B8C6FE252B3F` |
| [classroom/app/classroom_service/backup.py](E:/codex-work/sub2api/classroom/app/classroom_service/backup.py) | `F73A11D7198C28D2266CA27EAAFF61FD1799EFDE3486591D635EAB1D4A8332B6` |
| [classroom/scripts/Start.ps1](E:/codex-work/sub2api/classroom/scripts/Start.ps1) | `D29981A0D19A92AA6ED04A75A30C0C82E3DC0A8A88C7638306D30B125F6840D2` |
| [classroom/scripts/Build-Package.ps1](E:/codex-work/sub2api/classroom/scripts/Build-Package.ps1) | `E490C060BB8F604CD4DDBEFCF8DEF13F07218D61CFBF3363F4E6432C584B1811` |

源码范围和完整状态映射见 [配套检查表](E:/codex-work/sub2api/CLASSROOM_AI_AUDIT_CHECKLIST.md)。本轮审计新增的仅为这两份 Markdown 文档。

