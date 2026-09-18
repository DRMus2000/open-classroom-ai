# 课堂 AI 实施后逐项合规检查表

审计日期：2026-09-09  
审计对象：当前工作区和实际便携包目录；基线 Open WebUI 0.11.2 / Python 3.11.9。  
对应报告：[完整审计报告](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md)。原规格：[实施计划](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md)。

这份表按原计划的每条产品规则、默认值、B 节整改项、C—J 的编号/列表/数据字段/API、K 的全部测试用例、L 的全部阶段和总验收、七项交付物逐项映射。另有补充段落表覆盖正文中的事务、身份、可展示回答、源码及执行约束。原文的示例 JSON、文件树不被误当成新的独立功能；A 节既有事实与 C1 未选方案不要求“重新实现”，其实际约束已单列核对。

- **PASS**：该行限定的要求已有代码路径或实际测试证据。标明“核心”的 PASS 只证明该函数/事务，不代表整套产品可用。
- **PARTIAL**：有可复用实现，但存在未接通、语义不全或未完成必要验证的部分。
- **FAIL**：缺失必要实现，或已有反例/代码证据直接违反要求。
- **NOT VERIFIED**：现有证据不足以确认该行；没有把已知缺陷藏在未验证状态中。可选方案/可选提供商能力不强加为必须实现。

共 **475 行映射**：PASS 58、PARTIAL 247、FAIL 162、NOT VERIFIED 8。这是包含重复要求和字段级检查的覆盖索引，**不能用它直接计算产品合规百分比**。按原计划十二项总验收：0 PASS、8 PARTIAL、4 FAIL，严格通过率 **0/12 = 0%**；仅用于描述进度的折半权重为 **(0 + 8 × 0.5) / 12 = 33.3%**。Critical/High 不因平均分得到豁免。

问题编号是本轮报告编号，不能与原计划 B 节的同名旧问题编号混淆。“H06—H08”表示分别查阅对应三个问题。全部源定位链接指向审计时的准确行；后续修改代码后应重定位。

## 已确认的产品规则

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q001 · [L20](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:20) | R01；只服务一个约 30 人的班级，1 名教师，教师具有完整管理权限。无多班、多租户和教师分工需求。 | **PARTIAL** | 单班名册存在；教师管理被实际 middleware 封锁，完整 30 人 UI 未通过（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)）。 |
| Q002 · [L21](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:21) | R02；学生默认每天 3 次；每人独立；未使用次数不结转。按教师电脑操作系统时区对应的自然日计算，不能使用学生浏览器或学生个人资料的时区。 | **PARTIAL** | 日桶默认 3、独立归属已测；时区异常和自动过期不完整（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q003 · [L22](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:22) | R03；一次新的问答计一次，包括追问和明确发起的重新生成。首版每次只选一个课堂模型。HTTP 重传、刷新后重新订阅相同操作，不产生新计数和新模型调用。 | **PARTIAL** | 核心幂等/单模型有效；原生操作 ID、追问和刷新未接通（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)、[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)）。 |
| Q004 · [L23](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:23) | R04；教师拒绝扣 1 次；正常完成的回答扣 1 次。教师修改后批准仍是原请求，最多扣 1 次。 | **PARTIAL** | 核心拒绝/成功单次结算已测；实际执行链缺失，截断误判成功（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)）。 |
| Q005 · [L24](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:24) | R05；网络故障、模型错误、服务重启等导致的意外中断不扣，即使已经产生部分回答。不能沿用旧建议中的“所有部分输出均收费”。 | **FAIL** | 实际 HttpUpstream 将截断、错误 SSE 和空响应计 completed 并扣 1（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)）。 |
| Q006 · [L25](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:25) | R06；学生主动停止且已经有可展示回答，扣 1 次；尚无可展示回答时主动停止不扣。教师暂停、维护或故障造成的终止不冒充学生主动停止。 | **FAIL** | 按持久化而非已交付正文收费，停止不中断上游（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q007 · [L26](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:26) | R07；跨日仍待审：自动移出待审队列，标记已过期，释放预留额度；问题、附件及审计历史继续保留。这是用户对“自动删除”的最终澄清，不物理删除历史。 | **PARTIAL** | 过期函数保留历史且释放预留；启动/定时/查询没有自动执行（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q008 · [L27](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:27) | R08；教师可给单个学生或选中的多个学生调整今天的可用次数；有全选全班操作。以“+1、-1、自定义增减”为主，记录操作者、时间和原因。 | **PARTIAL** | 核心事务支持批量；HTTP 重传重复加次，UI 无全班/自定义完整流程（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q009 · [L28](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:28) | R09；批量导入学生账号和初始密码，强制首次登录改密；忘记密码由教师重置，重置后再次强制改密。暂不要求学号规则或学校统一身份系统。 | **FAIL** | 首次改密、原生登录及重置撤销存在实证缺口（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)—[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q010 · [L29](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:29) | R10；支持图片及用于 Python 教学的文本类附件；能够审核图片内容和文本文件全文。只带文件或图片的提问也必须审批；上传本身只是本地准备，不单独扣次或调用模型。 | **PARTIAL** | 本地 blob/文本读取有效；不可审附件、纯文件提问失败、原生上传可处理（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q011 · [L30](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:30) | R11；教师机始终联网；依赖仍随便携包提供，不要求本地离线模型。上游必须具备所启用的图像输入能力。 | **PARTIAL** | 复用便携依赖且不要求离线模型；图像能力检查和最终包未完成（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q012 · [L31](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:31) | R12；已提交问题、审批、调整记录、对话和相关附件永久保留，教师可以导出学生对话。学生不能通过删除聊天或临时会话使教师留存记录消失。 | **PARTIAL** | 新课堂记录有独立归档；旧聊天/审批/附件迁移导出未完成（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |

## 本期采用的具体默认值

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q013 · [L37](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:37) | 一个学生同一时刻最多一个活动请求，包括待审、已批准排队和生成中；换浏览器也不能增加。 | **PASS** | ClassroomService + BEGIN IMMEDIATE 限制单活动；同学生并发测试通过。此项仅指课堂提交核心，旁路另见 [C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)。 |
| Q014 · [L38](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:38) | 待审默认一直保留到当日结束；取消旧 Filter 的固定一小时业务过期规则。传输连接超时与业务过期是两回事。 | **PARTIAL** | expires_at 采用当地日界；自动清理未接运行生命周期（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q015 · [L39](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:39) | 上游并发初始为 4，可由教师设置为 1—8；30 人可以同时提交，实际生成按批准顺序排队。 | **PARTIAL** | 核心默认 4 且范围 1—8，正常 30 人模拟峰值 4；停止后实际并发失控，配置 UI 缺失（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q016 · [L40](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:40) | 连接超时 10 秒，首个可展示输出超时 60 秒，单次生成最长 300 秒；均作为可调整的运行配置。 | **FAIL** | 仅单 socket timeout，没有独立 10/60/300 秒生命周期控制（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q017 · [L41](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:41) | 全班暂停阻止新提交和新派发；已经生成中的请求默认继续。另设教师“停止生成”操作，按意外/管理中断处理，不扣学生次数。 | **PARTIAL** | 全班状态及禁止新领取的核心存在；已有教师 stop 路由但没有页面按钮，实际停止执行不完整（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q018 · [L42](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:42) | 每个学生可以单独暂停 AI 权限。调整次数不会自动解除暂停。 | **PARTIAL** | 个人状态字段和提交校验存在，调额不自动解禁；派发不重新检查，缺管理 UI（[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q019 · [L43](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:43) | 原生自动标题、标签、追问建议、自动补全、上下文 AI 摘要、自动搜索、工具调用、代码执行、语音、图像生成和多模型并行不纳入首版。Python 文件只作为教学材料传给模型，不在教师机执行。 | **FAIL** | 部分 URL 拒绝，但副入口和原生文件处理仍可外发（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q020 · [L44](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:44) | 教师可以设置课堂提示词和允许的模型；学生不能自由改系统提示词、接入自有提供商或启用额外插件。 | **FAIL** | 无受管课堂提示词/完整配置链，浏览器 system 可进入快照（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q021 · [L45](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:45) | 教师测试默认免审批、免学生额度，仍走相同的唯一模型出口并记录为教师测试。 | **FAIL** | 没有独立的教师免审批测试链及对应审计；正常教师模型路径也被封锁（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q022 · [L46](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:46) | 本期默认日额度固定为 3；单人/批量调整仅影响今天。没有直接清零使用历史的按钮，“补回机会”通过带审计的正向调整完成。 | **PARTIAL** | 默认 3、调整写 ledger 而不清 used 已实现；实际提交丢日期/幂等（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q023 · [L47](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:47) | 历史永久保留不等于无限制上传：实施附件大小限制、磁盘容量提示和备份，不自动删除已提交历史。 | **PARTIAL** | 部分文件大小限制和独立归档存在；磁盘提示、临时清理、完整备份未完成（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)、[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |

## B1. Critical：优先阻断审批绕过

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q024 · [L143](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:143) | C01；`OWUI/main.py:820—821` 挂载 OpenAI 路由；`routers/openai.py:1464` 的 /openai/chat/completions 接受普通学生，直接到上游，不调用课堂 Filter。已用实际 handler 和模拟上游复现。；学生所有模型调用必须进入唯一课堂执行出口；没有课堂授权的请求不得取得真实上游调用能力。 | **FAIL** | 原 /openai 前缀被拦，但所有出口封闭要求失败，messages/embeddings 已复现（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q025 · [L144](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:144) | C02；`OWUI/main.py:1448—1469` 在执行 Filter 前创建首次标题任务；tasks 路由另行调用模型。当前自动标题开启，因此原问题可能在审批前离开教师机。；禁止所有审批前模型副调用，包括标题、查询改写、自动摘要、嵌入、语音和工具模型调用；不是只修正文聊天。 | **FAIL** | 未验证或关闭全部审批前副调用；文件 process=true 可进入原生处理（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q026 · [L145](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:145) | C03；`app/open_webui_review_filter.py:87—91` 的 key 不绑定内容；`review_service.py:179—185` 重复 key 返回旧批准。批准无执行消费状态。已复现 A 获批后 B 放行、一个批准放行两次。；服务端请求快照、同 key 不同内容 409、唯一执行领取、状态持久化和幂等结算。 | **PARTIAL** | 核心同键异体冲突、单 claim 和终态唯一已测；分支关联不绑定、实际链未打通（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |

## B2. High：身份、生命周期、升级与数据

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q027 · [L151](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:151) | H01；Filter :58—84 只提取最后一条文字，没有文字就放行。纯图片已复现零审批调用；附件和上下文也不完整展示。；支持真实附件快照，缺失审核能力时拒绝；最终上游内容必须与批准快照一致。 | **PARTIAL** | 有不可变附件核心；原生接管、教师内容审核、纯文件 UI 未完成（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q028 · [L152](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:152) | H02；review_service :86—93 默认空令牌即不鉴权；本地可访问者有全部权限，单令牌也不区分服务与教师，缺少教师审计。仅本机绑定降低了 LAN 暴露，不能代替身份验证。；同源教师认证入口、内部服务认证、无匿名决策接口。 | **PARTIAL** | 新接口有教师依赖与 HMAC 工具，旧服务不由新 Start 启动；内部协议不完整且保留引导豁免（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q029 · [L153](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:153) | H03；review.html :48 优先显示昵称，而 auths/update/profile 允许学生改名，教师可能认错人；底层 user_id 并未被伪造。；教师维护的名册名 + 稳定用户 ID/登录标识；不依赖可编辑昵称归属额度。 | **PARTIAL** | 独立名册/稳定 ID 已实现；审核队列只显示 user_id，缺可识别名册信息（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q030 · [L154](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:154) | H04；Start.ps1 :49—57 在 bootstrap 前监听 LAN，首次部署有管理员抢注窗口；bootstrap 失败留下进程；下次 /health 都为 200 就跳过初始化。；先完成可信初始化和保护层自检，再开放学生使用；健康必须包含审批有效性。 | **FAIL** | 真实保护自检未接通，ready 可为真而入口未封闭（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q031 · [L155](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:155) | H05；bootstrap :63—72 每次依赖保存的教师旧密码；教师改密后失败；:135 打印密码，Start :56 保存到日志。；一次性初始化与日常启动分离，不长期保存/打印教师密码。 | **PARTIAL** | 新脚本不再打印/保存教师密码；仍每次要求密码 bootstrap，原发行指南未同步（[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q032 · [L156](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:156) | H06；当前持久配置公开注册为 true、默认角色 user；未来按账号计数会被多注册绕过。；关闭公开注册，所有可用学生必须进入教师维护的 enrollment。 | **PARTIAL** | 核心 enrollment 和部分 bootstrap 禁用意图存在；现有持久库仍开放注册，尚未完成关闭并读回验证（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q033 · [L157](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:157) | H07；review 服务仅三种状态；Filter :110—127 超时/取消不通知队列；Open WebUI 重启后等待任务消失而旧审批仍可操作。；C 节持久状态机、原子过期、取消、故障恢复；旧批准不能重用。 | **PARTIAL** | 有状态机；停止/过期/重启恢复实际运行缺失（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)—[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q034 · [L158](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:158) | H08；`OWUI/utils/auth.py:307—316` 无 Redis 时改密撤销令牌是空操作；此包没有配置 Redis，JWT 默认有效 4w。共享设备/密码泄露时旧令牌可继续使用。；H 节课堂会话登记与撤销，不仅缩短有效期；禁止绕过保护层的备用启动路径。 | **FAIL** | 原生 JWT 懒登记及 REST/WS 未覆盖，重置后未登记旧令牌可用（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q035 · [L159](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:159) | H09；run_openwebui.py :5—13 和 Start :41 禁用官方迁移，仅 create_all；当前库缺 alembic_version 和规范化邮箱迁移索引。升级不能据此保证兼容。；离线数据副本中建立可验证迁移基线，不允许未经分析直接 stamp head 或打开迁移。 | **FAIL** | 只有结构清单演练脚本与手动 marker，没有已验证基线修复/数据迁移（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[M05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M05)）。 |
| Q036 · [L160](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:160) | H10；Open WebUI 已保存用户原文，旧 Filter 只替换本次 body。修改后批准的内容、用户看到的历史及下次模型上下文存在不一致风险。；归档 original/effective 两份；后续上下文以已批准 effective 内容及已归档回答重建，不能悄悄回退原文。 | **FAIL** | 浏览器历史直接入快照，未从有效归档重建后续上下文（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |

## B3. Medium：并发、校验、运维

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q037 · [L166](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:166) | M01；review_service :181—188 先 SELECT 再 INSERT，相同请求并发时可能唯一约束异常；唯一约束防了重复行但错误未转换。；原子 UPSERT/冲突读取和请求幂等；返回稳定错误。 | **PASS** | 提交写事务串行化，冲突读取返回既有请求；已测并发幂等，不再是先查后写的旧竞争。 |
| Q038 · [L167](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:167) | M02；review_service :107 起未要求 JSON object，[] 导致 AttributeError；必填 null 被 str(None) 接受；长度、类型、读取超时不完整。；Pydantic/等效严格模式校验、正文限制、读取超时、速率限制。 | **PARTIAL** | 部分 payload/上传验证存在；JSON、类型、CSRF、大小/速率仍不足（[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q039 · [L168](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:168) | M03；无每人活动请求限制；每请求每秒轮询；列表 LIMIT 200 无分页，状态排序缺少专用索引。；单活动请求、有限上游并发、分页索引、SSE 或有退避的状态查询。 | **PARTIAL** | 活动限制/索引/核心游标存在；原生 API 不暴露游标，Pipe 同步轮询且执行并发有缺陷（[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q040 · [L169](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:169) | M04；Stop :3—11 只凭 PID 强杀；PID 复用可误停，备用文件名匹配漏 run_openwebui.py；Stop 不支持 Start 的 DataRoot。；PID + 命令行/可执行文件/实例标识验证；统一配置；正常停止及可恢复的强停。 | **PARTIAL** | 增加了部分 PID 路径/时间校验；缺实例锁、命令行身份、完整 DataRoot/排空（[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q041 · [L170](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:170) | M05；Scripts/open-webui.exe、pip.exe 内嵌不存在的打包机绝对路径；常用相对 Python 启动未受影响，但维护入口损坏。；使用相对解释器 + 模块/脚本入口，校验整个包可搬迁。 | **PARTIAL** | 部分新维护入口使用相对 python；完整 launcher、空格路径、最终便携验证失败（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)、[H19](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H19)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q042 · [L171](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:171) | M06；未发现完整课堂源码/打包锁定文件/恢复脚本；日志和附件无限增长缺管理，热拷贝 SQLite/WAL 不等于一致备份。；独立源码、锁定依赖、可复现打包、联合备份恢复和容量检查。 | **PARTIAL** | 独立源码和 Backup API 已加入；依赖全锁/全备恢复/容量管理未完成（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)—[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q043 · [L172](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:172) | M07；学生可以使用聊天删除、临时会话等功能；只依靠 Open WebUI 当前聊天库不能满足永久保留。；独立权威归档；限制学生物理删除，教师保留导出。 | **PARTIAL** | 课堂新请求独立留存；原生历史及删改后完整对话归档未接通（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |

## B4. Low：界面与易用性

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q044 · [L176](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:176) | review.html :54 中取消拒绝原因输入仍会拒绝；应真正取消操作。 | **PASS** | 新教师页对拒绝原因 prompt 的 null 返回取消；旧页面仍在发行目录，文档问题见 [L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)。 |
| Q045 · [L177](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:177) | decision fetch 没有完整网络错误处理，按钮缺少提交保护；修复后仍须依赖后端幂等。 | **PARTIAL** | 有 fetch 错误提示；缺提交锁、未知结果恢复与稳定操作键（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q046 · [L178](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:178) | UTC 原始时间显示应转换为教师机时区；队列显示准确总数、等待时间和可追踪错误。 | **FAIL** | 队列直接显示 UTC，缺等待时间/完整统计与时区显示（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q047 · [L179](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:179) | 保留现有成功设计：参数化 SQL、不可由学生关闭的全局 Filter、审批条件更新；双教师/双标签同时决定同一记录时第二次返回 409，不能误报为决策覆盖漏洞。 | **PARTIAL** | 参数化 SQL、版本决策和唯一结算保留且测试通过；旧全局 Filter 被关闭但替代保护不完整（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q048 · [L180](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:180) | 未对干净 Windows 电脑、30 人压力或真实模型做完整验收；不要把依赖检查通过写成上述测试已通过。 | **PARTIAL** | 实施报告确实披露阶段 8/9 未测；前面阶段的完成/集成声明仍过度（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |

## C1. 方案选择

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q049 · [L190](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:190) | 官方 Pipe 作为课堂模型，独立服务拥有唯一真实上游出口；推荐。Pipe 接收可信用户和完整模型输入；服务统一负责审核、执行、计数和留存。原生账号/聊天仍保留。 | **PARTIAL** | 已建立 Pipe 和服务组件；真实唯一出口与独立执行所有者未形成（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)—[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)）。 |

## C2. 组件职责

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q050 · [L212](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:212) | Open WebUI 保留学生聊天体验、账号密码哈希、角色和已有聊天。 | **PARTIAL** | 复用原生账号/库，未修改密码哈希；正常聊天被封锁，自建页不能替代会话体验（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q051 · [L213](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:213) | 课堂 Pipe 是学生唯一允许选择的模型入口，可以在服务端映射一个或多个教师允许的模型，但一次只调用一个。 | **FAIL** | Pipe 实际模型 ID 与策略不一致且存在其他出口（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)）。 |
| Q052 · [L214](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:214) | 真实提供商密钥只由课堂服务持有，不再留在学生可达的 Open WebUI 普通 OpenAI/Ollama 提供商配置中。清理前先迁移和验证，避免丢失原配置。 | **FAIL** | 未实现受管密钥迁移；Pipe 在 WebUI 进程直接持有/使用提供商凭据（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q053 · [L215](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:215) | 原 Filter 改为轻量附件准备/状态适配，不再独立收费、长期等待或持有第二套批准状态。 | **PARTIAL** | 有轻量 Filter 文件，但未安装且没有 file_handler，原生文件未接管（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q054 · [L216](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:216) | 课堂服务为唯一审批、额度及最终模型输入/输出的事实源。即使学生绕开界面直接请求 API，也只能被拒绝或经过同一事实源。 | **PARTIAL** | SQLite 作为课堂数据源存在；多个 Service、未接内部协议和旁路使唯一执行事实源失效（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q055 · [L217](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:217) | 3000 提供同源 `/classroom/*` 页面和 `/api/classroom/*` 桥接 API。8790 只保留内部服务端口并强制认证，匿名原审核页和匿名决策接口移除。 | **FAIL** | 课堂路由被根 SPA 遮挡；8790 仍承载另一份外部 API，内部协议仅 readiness（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q056 · [L218](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:218) | 单实例服务 + 本地 SQLite 足够作为本班初始架构；不为本期引入 Redis/PostgreSQL 集群。JWT 撤销按 H 节适配，不假装原生无 Redis 已解决。 | **PARTIAL** | SQLite/无 Redis 选择适合本期；单实例锁和原生会话撤销未实现（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |

## C3. 请求提交与批准绑定

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q057 · [L226](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:226) | 前端创建一个操作 UUID，作为重传幂等键持久在当前操作中；刷新重试沿用。它只是幂等标识，不是授权凭证。 | **FAIL** | randomUUID 不兼容默认 LAN HTTP，且当前操作不持久化（[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)）。 |
| Q058 · [L227](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:227) | 适配层验证原生用户、课堂会话、enrollment、首次改密状态及聊天/文件所有权。不能接受 body.user_id、姓名、IP 或 role 字段作为身份。 | **PARTIAL** | 原生依赖/学生 ID/附件归属部分有效；会话、必改、聊天/分支归属未完整校验（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q059 · [L228](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:228) | 只允许课堂 Pipe 模型。删除或拒绝学生输入中的内部上下文、服务身份、批准状态、工具、任意上游 URL 等控制字段。 | **PARTIAL** | 核心模型与一些控制字段检查存在；系统提示/历史权威性和实际入口仍失败（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q060 · [L229](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:229) | 文件在本地校验并生成不可变快照；组装最终模型、系统提示词、有效历史、当前文字、附件以及允许的生成参数。不得先调用 AI 来解析或摘要。 | **PARTIAL** | 本地附件和快照存在；缺有效历史/受管系统词及教师实际内容预览（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q061 · [L230](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:230) | 在服务端生成 request_id。计算规范化的输入指纹：绑定 user_id、操作键、会话/分支、模型与配置版本、完整实际上下文和附件内容哈希。 | **PARTIAL** | 服务端生成请求及 payload hash；chat/parent/message 关联和真实配置没有完整绑定（[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q062 · [L231](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:231) | 同一用户同一操作键、同一内容：返回既有请求；不同内容：409；学生另外生成操作键也仍受额度和活动请求限制。 | **PARTIAL** | 已测相同 payload 重传及异体冲突；更换分支关联不冲突（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q063 · [L232](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:232) | 在一个 SQLite 写事务内惰性建立当日额度桶，校验剩余和全班/学生状态，预留一次，写入 pending 请求和审计。 | **PASS** | 核心日桶、预留、请求、reserve ledger 在同一短写事务，正常并发测试通过。 |
| Q064 · [L233](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:233) | 学生显示“待教师审核”“可用/预留次数”，教师看到最新文字、图片、文本附件、模型和可展开的完整有效上下文。 | **PARTIAL** | 额度/待审文字可见；图片/文件全文及完整有效上下文展示缺失（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q065 · [L234](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:234) | 教师决定必须携带 expected_version；事务中重新判断是否跨日、是否已终结及相关权限。 | **PASS** | 核心 decision 要求版本并事务内检查终态/过期；现有决策测试通过。页面路由可达性另见 [H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)。 |
| Q066 · [L235](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:235) | 批准记录具体快照版本与 digest。修改后批准生成新的 effective 快照，并绑定该版本；保留原问题。教师若需要移除附件，必须在 UI 明确操作并产生新快照，不能因改文字而意外丢附件。 | **PARTIAL** | original/effective 快照、改写保留附件有核心实现；没有明确附件编辑 UI/完整配置绑定（[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q067 · [L236](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:236) | 从批准到发送不能重新加载可能变化的附件、模型配置或系统提示词。派发前再次校验授权、暂停状态及快照。配置变化使待执行批准失效时退回待审并提示，不能静默换模型。 | **FAIL** | 派发不重新检查个人暂停/安全状态/配置，移除模型仍可再次批准发送（[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)）。 |
| Q068 · [L237](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:237) | 上游工作进程只领取一次执行权，只发送已保存的 effective payload。禁止批准后由另一个调用者携带新 body 替换。 | **PARTIAL** | 唯一 claim 与保存 payload 的核心已测；运行中无调度器，未核验派发摘要/当前授权（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)）。 |

## C4. 状态与额度结算

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q069 · [L247](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:247) | 校验失败、无额度、暂停、未改密；预留 0；正式使用 0；上游 0 | **PARTIAL** | 核心提交可拒绝无额度/暂停/必改；原生旁路和上传限制失败（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q070 · [L248](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:248) | pending；预留 1；正式使用 0；上游 0 | **PASS** | 直接核心提交结果 pending、预留 1、未收费且未调用上游，测试通过。 |
| Q071 · [L249](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:249) | rejected（教师拒绝）；预留 0；正式使用 1；上游 0 | **PASS** | 核心拒绝收费 1、释放预留、零上游，重复结算受唯一约束保护。 |
| Q072 · [L250](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:250) | approved_queued；预留 1；正式使用 0；上游 尚未调用 | **PARTIAL** | 核心批准仅排队和保留预留；实际没有运行 worker 消费（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q073 · [L251](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:251) | generating；预留 1；正式使用 0；上游 最多 1 次派发 | **PARTIAL** | 核心 claim/attempt 唯一已测；停止后执行仍存活及真实流程未接通（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q074 · [L252](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:252) | completed；预留 0；正式使用 1；上游 已正常结束 | **PARTIAL** | 正常模拟完成收费 1；错误流也被误判 completed（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)）。 |
| Q075 · [L253](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:253) | cancelled_before_output；预留 0；正式使用 0；上游 未发送或没有可展示输出 | **PARTIAL** | 未写正文的停止零扣可用；竞争时未真正停止或释放真实调用（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q076 · [L254](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:254) | stopped_by_student_after_output；预留 0；正式使用 1；上游 已有可展示回答，学生主动停止 | **FAIL** | 只看写入正文，不看有效订阅交付，未接实际取消（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q077 · [L255](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:255) | interrupted；预留 0；正式使用 0；上游 已有输出也不扣；标记故障来源 | **PARTIAL** | 显式上游异常零扣已测；截断/SSE error 被遗漏（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)）。 |
| Q078 · [L256](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:256) | expired；预留 0；正式使用 0；上游 不得发送 | **PARTIAL** | 直接 expire_pending 会正确终结；正常查询/启动不自动清理（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q079 · [L257](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:257) | interrupted_unknown；预留 0；正式使用 0；上游 无法确认故障前上游执行结果；不得自动重发 | **PARTIAL** | 显式 unknown 故障/恢复函数零扣不重发；重启实际未调用恢复（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |

## C5. 重试、断网、刷新与重启

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q080 · [L269](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:269) | 浏览器刷新/暂离本身不是学生主动取消，也不必然表示生成失败。若后台完成且结果可恢复，按成功一次处理；如果底层确实中断，按 interrupted 零次处理。 | **PARTIAL** | 核心可保留终态和事件；浏览器恢复及断线心跳没有真实闭环（[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q081 · [L270](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:270) | 页面恢复先按 request_id 查询状态并重放已经持久化的回答事件，不能再次发送上游 POST。 | **PARTIAL** | after_seq 读取和重放核心存在；页面只恢复 pending，操作标识不持久（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)、[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)）。 |
| Q082 · [L271](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:271) | 学生主动点停止先调用课堂 cancel/stop API；由服务停止上游并结算，再取消 Open WebUI 消费任务。绕过该 API 调用原生 task stop 时，适配层也必须关联到同一 request_id，不能遗漏或误判成网络故障。 | **FAIL** | cancel 不取消上游；原生 task stop 无关联适配（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q083 · [L272](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:272) | 断线检测/消费租约过期使任务确实终止时，由服务记录故障，释放预留，归档部分回答并标记“不完整”。 | **FAIL** | consumer heartbeat 无调用者，lease 清理未接运行生命周期（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q084 · [L273](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:273) | 课堂服务重启：pending 同日可恢复，过期则终结；已批准但确知尚未派发的可重新排队；generating 或派发结果不明的记 interrupted_unknown、释放预留，不自动重发。 | **FAIL** | 新建 Service 不执行恢复，旧 generating 占预留但 ready（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q085 · [L274](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:274) | 原生 WebUI 重启：通过关联心跳和实例标识使执行任务停止/确认状态；挂起操作可查询恢复，不能用新 message_id 重新获得旧批准。UI 记录恢复不应重新调用 AI。 | **FAIL** | 缺跨 WebUI 实例心跳与安全停止/恢复协议（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q086 · [L275](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:275) | “重试相同操作”指请求状态重取/响应重放。已终结失败后的“重新提问”明确创建新操作并重新审核；失败的旧操作仍为零使用。界面不能在用户不知情时自动新建。 | **PARTIAL** | 核心同操作返回旧状态；UI 每次提交新键，刷新/失败语义未完整处理（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)、[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)）。 |
| Q087 · [L276](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:276) | 即使服务在“写派发标记”和“发出 HTTP”之间崩溃，也不能宣称外部调用 exactly-once。保守标记结果不明、零扣费、无自动重发；上游实际费用可能已产生，与课堂次数分开。 | **PARTIAL** | 有派发标记和未知结果零扣不重试逻辑；实际崩溃恢复没有触发（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q088 · [L277](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:277) | 上游支持幂等键时可额外传递 request_id，但不能假设所有 OpenAI 兼容提供商都支持。 | **NOT VERIFIED** | 上游幂等键属于可选额外能力；没有对当前真实提供商支持情况做验证，也未据此宣称 exactly-once。 |
| Q089 · [L278](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:278) | 每人活动请求上限、全局并发和提交速率限制用于减轻反复取消/故障占用，不得通过偷偷扣次数替代用户的零扣费规则。 | **PARTIAL** | 单活动限制存在；真实并发槽提前释放、无速率限制（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |

## C6. 时区、日界和人工调整

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q090 · [L282](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:282) | Windows 上优先用已打包 tzlocal 取得教师机 IANA 时区，使用 zoneinfo + tzdata 计算自然日边界；不能只保存固定 UTC+8 偏移。 | **PARTIAL** | tzlocal/zoneinfo/tzdata 与本机时区测试存在；探测失败静默 UTC 不合规（[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q091 · [L283](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:283) | 全部事件保存 UTC 时间，同时日桶保存 quota_date、当时的 timezone_id 和配置版本。过期时间是下一个当地自然日零点换算的 UTC 时刻，不是简单加 24 小时。 | **PASS** | UTC 事件、日桶时区快照、按当地下一日零点计算过期的核心已核对。 |
| Q092 · [L284](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:284) | 服务重启读取教师机时区，检测变化并记录系统审计；历史日桶不重算。相同 user_id + 日期复用同一日桶，不因为时区版本变化再发一份额度。 | **PARTIAL** | 时区变更审计/同日期主键已实现；实际 Windows 切换/异常边界尚未完整测（[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q093 · [L285](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:285) | 时区无法识别或系统时钟异常倒退导致业务日期不可信时，暂停新扣留/派发，显示可操作错误；不得偷偷按学生时区或 UTC 建桶。 | **FAIL** | 无可靠时区/时钟回退时没有暂停保护（[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q094 · [L286](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:286) | 日桶字段：base_limit、adjustment、used、reserved；`available = base_limit + adjustment - used - reserved`。 | **PASS** | 日桶公式及 reserve/used/adjustment 分离已测。 |
| Q095 · [L287](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:287) | 第一次在某日观察到请求时即可创建该日桶，不依赖午夜必须开机；服务次日才启动时，恢复事务先终结所有过期待审，再允许新提交。禁止“进程启动就重新发 3 次”。 | **PARTIAL** | 惰性日桶不因重启重复发放；启动先清理过期待审缺失（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q096 · [L288](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:288) | +1/-1 增减 adjustment，不能直接改 used 或删除 ledger。减少后 available 不能小于 0，不能取消已经预留的请求。 | **PASS** | 核心调整只增减 adjustment，有非负/预留检查及 ledger；已测不足时回滚。 |
| Q097 · [L289](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:289) | 批量默认全有或全无：先预览全部选中学生的前后次数，提交时一个事务重新校验版本。任一学生不合法则整批 409/422，明确说明，没有悄悄部分成功。 | **PARTIAL** | 核心有全有全无事务；实际接口和 UI 不强制预览版本（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q098 · [L290](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:290) | 每次调整带独立幂等键、教师 ID、原因及每人前后值。默认原因可为“课堂临时调整”，教师可改。 | **PARTIAL** | 核心独立 key、教师、原因和前后值存在；HTTP header 被丢弃导致重传重复应用（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q099 · [L291](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:291) | 不做复杂长期套餐和班级共享额度。以后如果支持默认日额度修改，应对未来日桶生效，另立需求。 | **PASS** | 未引入长期套餐或共享额度；默认日限 3，调整为当日 adjustment。 |

## D1. classroom_settings / schema_migrations

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q100 · [L301](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:301) | key、value_json、version、updated_at、updated_by；单班配置及审计关联，包括暂停、并发、超时、模型清单和附件限制。 | **PARTIAL** | settings 表和暂停/允许模型部分使用；并发/超时/图像能力/受管系统词无完整统一配置（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q101 · [L302](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:302) | detected_timezone、timezone_revision；教师机当前时区与变更版本；不是学生配置。 | **PARTIAL** | 教师时区及版本写入和变更审计存在；异常探测不暂停（[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q102 · [L303](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:303) | schema_version、migration_checksum、applied_at；自有数据库迁移记录，可验证版本与脚本一致。 | **PARTIAL** | 自有 schema_version/checksum 存在；验证先执行 DDL，VerifyOnly 写库（[M05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M05)）。 |

## D2. students

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q103 · [L311](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:311) | user_id（PK）；原生不可变 Open WebUI 用户 ID；额度归属的唯一依据。 | **PASS** | students 以原生 user_id 为主键；核心并发中 30 个学生额度独立。 |
| Q104 · [L312](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:312) | roster_name、login_identifier；教师管理的显示姓名和实际 email 登录标识，脱离可编辑昵称。 | **PASS** | 名册名/login 单独保存，额度按 user_id，未依赖学生昵称。 |
| Q105 · [L313](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:313) | default_daily_limit；本期统一初始化为 3，保留扩展能力但不提供长期额度 UI。 | **PASS** | default_daily_limit 初始化 3，核心日桶测试通过。 |
| Q106 · [L314](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:314) | ai_enabled；单人暂停开关。 | **PARTIAL** | ai_enabled 可写并阻止新提交；不阻止已批准任务派发，缺教师入口（[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q107 · [L315](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:315) | enrollment_state；provisioning、active、disabled、deleted_origin；缺登记的普通账号不能调用课堂模型。 | **PARTIAL** | 字段和提交 active 校验存在；provisioning/删除角色事件未落地（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)、[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q108 · [L316](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:316) | created_at、updated_at；名册建立与修改时间。 | **PASS** | 创建/修改名册写 created_at/updated_at。 |

## D3. security_states / classroom_sessions

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q109 · [L324](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:324) | security_states.user_id（PK）；教师和学生均可有安全状态。角色仍以原生实时校验为准。 | **PARTIAL** | 教师/学生安全行存在；角色和安全状态没有统一覆盖原生 REST/WS（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q110 · [L325](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:325) | must_change_password；首次导入和管理员重置后的必改标记。 | **PARTIAL** | 必改字段存在；首次改密可绕过且上传未限制（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q111 · [L326](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:326) | credential_operation_state；ready、initializing、reset_in_progress、reset_failed；非 ready 状态默认禁止学生使用。 | **FAIL** | credential_operation_state 仅定义/默认 ready，实际导入重置未用安全操作状态（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q112 · [L327](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:327) | auth_epoch；每次改密、重置、注销全部会话增加；使旧课堂会话失效。 | **PARTIAL** | 自签会话 epoch/revoke 测试通过；原生 hook 缺失、旧 JWT 可懒登记（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q113 · [L328](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:328) | password_changed_at、reset_by、updated_at；安全操作记录，不存密码。 | **PARTIAL** | 安全记录不存密码；实际重置/改密顺序和完整记录不符合协议（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q114 · [L329](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:329) | sessions.token_fingerprint（PK）、user_id、epoch；原生登录令牌的 SHA256 指纹，登记其所属安全代次；不存原始令牌。 | **PARTIAL** | 存指纹/epoch 不存原令牌；登记时点错误，不能据表存在判安全完成（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q115 · [L330](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:330) | issued_at、expires_at、revoked_at、last_seen_at；短期课堂会话有效期与撤销/清理。 | **PARTIAL** | 时间字段存在；原生登记路径不检查 expires_at，13 小时仍有效（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |

## D4. daily_quotas

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q116 · [L338](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:338) | user_id、quota_date（联合 PK）；每学生每自然日唯一日桶；不把 timezone_revision 放入主键制造双份额度。 | **PASS** | 联合主键 user_id/quota_date，时区版本不制造第二份日桶；核心测试通过。 |
| Q117 · [L339](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:339) | timezone_id、timezone_revision；创建日桶时的教师时区快照。 | **PASS** | 创建时持久化 timezone_id/revision，历史桶不重建。 |
| Q118 · [L340](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:340) | base_limit、adjustment；当日基础额度快照及教师增减总和。 | **PASS** | base/adjustment 快照与调整流程已测。 |
| Q119 · [L341](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:341) | used、reserved；正式使用量和活动请求预留量。 | **PASS** | used/reserved 分开且各自非负；终态更新与 ledger 同事务。 |
| Q120 · [L342](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:342) | version、created_at、updated_at；并发校验与诊断。 | **PASS** | 日桶 version/时间字段参与核心调整；HTTP 不传版本属于 [H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)。 |

## D5. review_requests

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q121 · [L350](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:350) | id（UUID PK）、user_id；服务端请求及可信归属。 | **PASS** | 服务端 UUID 与可信 user_id 建请求，非浏览器授权。 |
| Q122 · [L351](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:351) | client_operation_id、client_payload_digest；重传关联及防止同键替换请求；唯一约束为 user_id + operation_id。 | **PARTIAL** | payload 指纹和串行幂等有实现；缺数据库 user+operation 唯一约束（[M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)）。 |
| Q123 · [L352](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:352) | chat_id、user_message_id、assistant_message_id、parent_request_id；原生聊天、两类消息和分支关系，正确恢复/导出/构建上下文。 | **FAIL** | 关联字段仅存储，原生聊天/两类消息/分支归属和上下文未接通（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q124 · [L353](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:353) | quota_date、timezone_id；固定归属日桶。 | **PASS** | 请求保存提交日/timezone，核心终态按原日结算。 |
| Q125 · [L354](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:354) | status、version；C4 状态与乐观并发控制。 | **PARTIAL** | 状态/version 核心可用；实际执行、恢复和停止语义有缺陷（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)—[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q126 · [L355](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:355) | original_snapshot_ref、effective_snapshot_ref、effective_digest；原始和实际批准模型输入的不可变归档引用及哈希。 | **PARTIAL** | 原始/有效 JSON 快照和 hash 存在；派发不核验 digest，历史未重建（[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q127 · [L356](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:356) | provider_profile_id、provider_profile_version、model_id；本次批准使用的具体上游配置版本；不含密钥。 | **PARTIAL** | provider/profile/version 字段存在；真实受管配置、失效后重审不完整（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)）。 |
| Q128 · [L357](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:357) | submitted_at、expires_at、decided_at、started_at、finished_at；UTC 生命周期；pending 过期时间为提交日结束。 | **PARTIAL** | 生命周期时间字段写入；自动到期与重启恢复不运行（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q129 · [L358](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:358) | decision_actor_id、decision_kind、decision_note；教师的 approve/reject/edit 及原因。 | **PASS** | 核心记录 actor/kind/note，版本化决策测试通过。 |
| Q130 · [L359](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:359) | reservation_state、charge_units、charge_reason；预留 open/released/consumed；终态次数只能 0 或 1，原因可追查。 | **PASS** | 预留 open/released/consumed 和 charge 0/1 有约束、终态 ledger 唯一；错误分类另见 [H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)/[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)。 |
| Q131 · [L360](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:360) | error_code、interruption_source；规范化错误和区分学生主动停止、网络、上游、维护、重启。 | **PARTIAL** | 中断字段存在；截断误判完成、真实管理停止/恢复未接（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)—[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q132 · [L361](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:361) | legacy_id、legacy_status、provenance；旧记录保留来源，不能把旧 approved 当成新执行授权。 | **FAIL** | legacy 字段只是预留，没有旧审批导入或 provenance 导出闭环（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## D6. execution_attempts / response_events

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q133 · [L369](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:369) | attempts.id、request_id（唯一）；本期一个已批准操作最多一个对外派发尝试；传输重连不新建 attempt。 | **PASS** | request_id 唯一 attempt，核心两个消费者只领取一次，正常并发已测。 |
| Q134 · [L370](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:370) | worker_instance_id、claim_token、claimed_at、lease_expires_at；唯一领取和服务重启/失联识别；claim_token 不是学生凭据。 | **PARTIAL** | worker ID/claim_token/lease 字段存在；心跳/启动协调没有生产调用（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q135 · [L371](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:371) | dispatch_state、dispatch_marked_at、first_output_at、ended_at；分辨未派发、派发结果不明、生成和结束。 | **PARTIAL** | 派发前标记存在；真实重启未按标记完成安全恢复（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q136 · [L372](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:372) | upstream_request_id；提供商返回的关联 ID（若有），不作为授权。 | **NOT VERIFIED** | 预留 upstream_request_id 字段；没有真实提供商关联 ID 契约验证，不阻断零重试原则。 |
| Q137 · [L373](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:373) | output_ref、finish_reason、termination_source；已生成的完整或部分可展示输出和结束分类。 | **PARTIAL** | 请求输出有持久正文；finish/termination 未可靠识别截断、停止和空流（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q138 · [L374](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:374) | response_events.request_id、seq（联合唯一）、event_type、payload_ref、created_at；可重放的流式事件；按 seq 续订，不向上游重新调用。 | **PASS** | 核心 events 按 request_id+seq 唯一持久保存，after_seq 重放不再调用上游。 |
| Q139 · [L375](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:375) | delivered_seq、consumer_lease；判断已交付的正文和消费端失联；不要仅靠客户端自报做授权。 | **FAIL** | 没有 delivered_seq 交付事实；consumer_heartbeat 无调用路径（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |

## D7. quota_ledger / teacher_actions

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q140 · [L383](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:383) | ledger.id、user_id、quota_date、request_id（可空）；日桶及相关问题。 | **PASS** | ledger 保存用户、日期、请求关联，与日桶事务写入。 |
| Q141 · [L384](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:384) | kind；reserve、settle_consumed、settle_released、teacher_adjust；退款若用于人工纠错须另记关联事件。 | **PASS** | reserve/settle_consumed/settle_released/teacher_adjust 分类存在。 |
| Q142 · [L385](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:385) | delta_reserved、delta_used、delta_adjustment；可重放计算的有符号整数。 | **PASS** | 有符号增量与 reserve/settle/adjust 一致，正常核心测试通过；完整启动对账另见 [M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)。 |
| Q143 · [L386](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:386) | actor_id、reason、created_at、operation_key；人工或系统来源、幂等与审计。 | **PARTIAL** | actor/reason/time/key 在核心存在；HTTP 调额不使用请求头 key（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q144 · [L387](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:387) | batch_id、before_json、after_json；批量操作关联和前后结果。 | **PASS** | 核心批量保存 batch_id/before/after，失败事务回滚已测。 |
| Q145 · [L388](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:388) | teacher_actions.id、actor_id、action、target_ids、result、created_at；审批、暂停、重置、导入、导出等通用审计。 | **PARTIAL** | 有通用审计和部分操作记录；缺失的导入恢复、实际停止/模型配置流程无完整审计（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |

## D8. attachments / snapshots

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q146 · [L396](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:396) | attachment_id、owner_user_id、request_id、source_file_id；不可变附件、原生文件来源和归属。 | **PARTIAL** | 本地 owner/request 关联验证存在；source_file_id 原生适配未接（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q147 · [L397](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:397) | original_filename、media_type、size_bytes、sha256；展示与校验；文件名不是存储路径。 | **PASS** | 文件名与哈希存储路径分离，服务端实算 sha256/size，核心不可变附件测试通过。 |
| Q148 · [L398](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:398) | blob_ref、normalized_ref、text_encoding；私有原始文件、规范化用于模型的内容及文本编码。 | **PARTIAL** | blob/文本编码实际保存；教师下载/预览未接，规范化预览不完整（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M01)）。 |
| Q149 · [L399](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:399) | image_width、image_height、preview_ref；图像解码限制和教师预览。 | **FAIL** | 只有头部尺寸提取，没有完整图像解码和 preview_ref 生成（[M01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M01)）。 |
| Q150 · [L400](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:400) | created_at、retention_class；已提交永久归档和未提交临时上传区分。 | **PARTIAL** | 时间/保留字段存在；未提交上传默认 permanent，无临时引用清理（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q151 · [L401](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:401) | snapshot_ref、schema_version、sha256、created_at；原始/有效上下文与输入的规范化版本。 | **PASS** | original/effective 快照带 schema_version、sha256、创建时间；核心保存/读取已测。 |

## D9. account_imports / import_rows / exports

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q152 · [L409](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:409) | imports.id、teacher_id、source_digest、created_at、status、summary；导入批次、来源指纹及结果，不保存原始带密码 CSV。 | **PARTIAL** | 批次/源 hash/状态持久保存、不落密码 CSV；重启恢复和已完成重放不完整（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q153 · [L410](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:410) | rows.batch_id、row_number、normalized_login、roster_name、status、user_id、error_code；逐行幂等与恢复；无 password 字段。 | **PARTIAL** | 逐行结构有记录且无 password 列；全无效提交结果可丢行，创建崩溃窗口未恢复（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q154 · [L411](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:411) | exports.id、teacher_id、filter_json、format_version、status、file_ref、sha256、created_at；导出可追踪、可校验、不重复生成。 | **FAIL** | 没有 exports 持久任务表/进度查询、结果 hash/可靠幂等任务（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |

## D10. 事务与一致性要求

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q155 · [L417](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:417) | SQLite 使用本地磁盘、WAL、busy_timeout、foreign_keys，关键写事务 BEGIN IMMEDIATE；每个事务持有时间短。 | **PASS** | 本地 SQLite、WAL、busy_timeout、foreign_keys、BEGIN IMMEDIATE 已核对；文件库模拟并发通过。 |
| Q156 · [L418](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:418) | 禁止持有数据库写锁等待 HTTP、教师决定、文件解析、密码哈希或上游生成。 | **PASS** | 正常核心业务未持有写事务等待教师或上游网络；HTTP 在 claim 事务之外。 |
| Q157 · [L419](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:419) | 预留、请求创建、ledger 一起提交；决策、终态结算、ledger 一起提交；批量调整同理。 | **PASS** | 预留/请求/ledger、决策/settle、批量调整事务原子性已测。 |
| Q158 · [L420](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:420) | 文件对象可先写入准备区，再在事务中发布引用；故障产生的未引用准备对象可以回收，不能反向删除正式归档。 | **PARTIAL** | blob 临时写入/原子发布和快照引用存在；临时对象回收、引用一致性保护不完整（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)、[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q159 · [L421](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:421) | 两个独立数据库没有分布式事务。账号导入/重置用 provisioning/operation 状态及幂等补偿恢复，不通过假设“两个 API 都会成功”实现。 | **FAIL** | 导入/重置直接假定跨库顺序成功，没有安全 provisioning/operation 恢复（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q160 · [L422](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:422) | 单实例排他锁和实例 ID 防止重复启动两个消费器；数据库约束仍作为最终防线。 | **FAIL** | 没有实例排他锁；多个运行组件各自建 Service（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q161 · [L423](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:423) | 上线前核对 daily_quotas 与 ledger 聚合完全一致；有差异时暂停新执行，提供诊断，不静默清零。 | **FAIL** | ready 只有 SQLite quick_check，无 ledger 对账或错误账目暂停（[M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)）。 |

## E1. 通用约定

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q162 · [L431](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:431) | JSON 请求只接受 application/json 和对象；未知关键控制字段拒绝。附件使用专门 multipart 入口。 | **PARTIAL** | 部分 object/字段检查存在；Content-Type/严格 schema/未知字段不全，上传采用无充分边界的 JSON base64（[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q163 · [L432](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:432) | Cookie 会话的写请求校验 CSRF 与 Origin；Authorization 模式也需明确定义跨源策略。内部端口没有“因为 localhost 所以匿名”的例外。 | **FAIL** | 缺 CSRF/Origin 校验；内部 HMAC 未覆盖实际业务，localhost 引导豁免长期存在（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)）。 |
| Q164 · [L433](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:433) | 非查询操作支持 Idempotency-Key；修改既有状态携带 expected_version。服务重新验证真实权限和归属。 | **PARTIAL** | 提交/决定有幂等和版本核心；调额头丢弃，其他写入无统一契约（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q165 · [L434](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:434) | 错误统一为 `{"error":{"code":"QUOTA_EXHAUSTED","message":"今日可用次数不足","request_id":"...","retryable":false}}`，无堆栈、密钥和原始内部响应。 | **PARTIAL** | ClassroomError 有统一 error 包装；类型异常仍可 500，部分原生错误直接返回（[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)）。 |
| Q166 · [L435](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:435) | 401 未登录/会话撤销；403 权限或课堂暂停；409 幂等、版本、已决策或过期冲突；413 过大；422 内容/附件/无额度校验失败；428 必须先改密；429 速率限制；503 保护组件未就绪。 | **PARTIAL** | 主要业务错误码存在；428/503 等未在全入口一致强制，没有 429 速率限制（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q167 · [L436](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:436) | 无额度统一使用 422 + QUOTA_EXHAUSTED，与请求速率 429 区分。前端不得只按状态码猜原因。 | **PASS** | 核心无额度返回 QUOTA_EXHAUSTED/422，未混作速率限制。 |
| Q168 · [L437](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:437) | 查询支持 cursor/limit，默认 50、最大 100；时间返回 UTC 与 quota_date、timezone，界面在教师/课堂指定时区展示。 | **PARTIAL** | 核心支持游标/部分限制；实际原生路由不接 cursor，队列时间/时区和稳定分页不足（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q169 · [L438](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:438) | 每次请求上限、分页和 ID 数量有明确校验；单班批量最多处理当前 30 名 enrolled 学生，不允许角色 admin 混入学生额度调整。 | **PARTIAL** | 调额核心限制 30 与学生名册；边界类型、所有列表和请求体上限不统一（[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |

## E2. 学生接口

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q170 · [L444](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:444) | GET /me；返回原生可信 ID、名册名、首次改密状态、课堂暂停及当日额度；不返回秘密。 | **PARTIAL** | 返回名册/额度/必改信息；active_request 只含 pending，路由被 SPA 遮挡（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q171 · [L445](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:445) | POST /account/change-initial-password；验证当前初始密码、新密码不同且满足规则；调用原生改密后完成安全状态并要求重新登录。 | **FAIL** | 相同新旧密码/原生 200 false 可清标记，无统一安全操作（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q172 · [L446](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:446) | GET /requests?scope=mine；本人问题历史、状态、计数及关联聊天。忽略/拒绝学生传入别人的 user_id。 | **PARTIAL** | 本人 ID 由依赖取得；没有 cursor/完整关联，且实际路由被遮挡（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q173 · [L447](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:447) | GET /requests/{id}；本人问题详情、原始/有效文字、附件引用、处理说明。 | **PARTIAL** | 本人详情和 original/effective 引用存在；附件内容/原生会话未完整接通（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q174 · [L448](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:448) | GET /requests/{id}/events?after_seq=N；以本人身份订阅持久事件，可恢复回答。 | **PARTIAL** | 事件按 seq 可读且限本人；没有真正持续 Pipe 流/消费心跳及完整 UI 恢复（[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q175 · [L449](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:449) | POST /requests/{id}/cancel；主动取消/停止；关联到实际执行状态，按 R06 结算。 | **PARTIAL** | 取消接口存在；不真实取消 HTTP、交付计数和竞争有缺陷（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q176 · [L450](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:450) | POST /attachments；受限图片/文本上传及验证；不执行 RAG 或文件内代码。 | **PARTIAL** | 本地受限上传不执行代码；必改状态仍可上传、未强制原生 process=false（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q177 · [L451](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:451) | GET /attachments/{id}/content；本人附件或当前请求授权文件，禁止越权和任意本地路径。 | **FAIL** | 两份课堂 API 均没有附件 content 下载/预览路由（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |

## E3. 教师接口

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q178 · [L480](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:480) | GET /admin/students；名册、今日 used/reserved/available、暂停和首次改密状态。 | **PARTIAL** | 原生教师依赖及列表存在；路由被遮挡，界面列信息不全（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q179 · [L481](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:481) | PATCH /admin/students/{id}；修改名册名、ai_enabled；不把普通用户自改昵称同步为名册身份。 | **FAIL** | 有 service.set_student_state，实际原生 router 无 PATCH 管理入口（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q180 · [L482](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:482) | GET /admin/requests；按状态、学生、日期查询全部问题，pending 按提交时间及 ID 排序。 | **PARTIAL** | 支持状态/学生/limit；日期/cursor/完整分页缺失，实际路由不可达（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q181 · [L483](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:483) | POST /admin/requests/{id}/decision；`decision: approve/reject/edit`，expected_version，note，修改文字及明确附件操作；决定完整快照。 | **PARTIAL** | 版本决定和 edit 核心存在；UI 无修改后批准及附件明确操作（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q182 · [L484](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:484) | POST /admin/requests/bulk-decision；教师明确选中记录批量通过/拒绝；每条带版本并返回结果。审批批量允许逐条冲突报告，不把整批错误地重复扣费；与额度批量的原子规则区分。 | **FAIL** | 未实现批量审批路由与逐条冲突 UI（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q183 · [L485](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:485) | POST /admin/quotas/preview；user_ids、delta、date，显示前后值及不可执行原因，不产生调整。 | **PARTIAL** | 预览可计算前后值；接口不绑定教师传入日期/后续版本（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q184 · [L486](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:486) | POST /admin/quotas/adjust；user_ids、delta、date、reason、expected_versions；整批事务，教师本人由会话取得。 | **FAIL** | 实际头幂等键被丢弃，日期/expected_versions 不强制，重传重复调额（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q185 · [L487](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:487) | PUT /admin/classroom/state；paused、reason；启停课堂，记录审计。 | **PARTIAL** | 后端课堂暂停写审计；UI 无开关，保护/停止链不完整（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q186 · [L488](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:488) | POST /admin/requests/{id}/stop；教师中止执行，按管理中断零扣费，不模拟学生动作。 | **PARTIAL** | 原生 router:149 已有教师 stop 并传 source=teacher；cancel 不真实中断上游，且页面无按钮（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q187 · [L489](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:489) | POST /admin/accounts/import/preview；解析受限 CSV，检查冲突与角色，返回无密码的逐行预览和短期批次凭证。 | **PARTIAL** | 标准 CSV 和无密码预览存在；已有原生邮箱冲突/完整逐行验证不足（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q188 · [L490](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:490) | POST /admin/accounts/import/{id}/commit；提交对应已预览批次；只建 user/pending 过渡账号，执行首次改密协议。 | **PARTIAL** | 实际 commit 直接创建 user；不具备 pending 安全过渡和可重放批次（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q189 · [L491](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:491) | GET /admin/accounts/import/{id}；显示逐行结果、错误和待恢复状态。 | **FAIL** | 没有 import/{id} 查询/恢复 API（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q190 · [L492](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:492) | POST /admin/students/{id}/reset-password；临时新密码或生成策略；封锁会话后调用原生管理员重置，要求学生再改。 | **FAIL** | 先原生改密再撤销，失败窗口与原生管理重置 hook 缺失（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q191 · [L493](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:493) | GET /admin/students/{id}/conversations；原生 API 与课堂归档组合查询，标明来源、分支和完整性。 | **FAIL** | 没有原生与课堂组合的 conversations 查询（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q192 · [L494](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:494) | POST /admin/exports；学生 ID 集合、日期、是否带附件；生成教师下载 ZIP。 | **PARTIAL** | 能生成新课堂记录 ZIP；日期/选定范围 UI、旧聊天、流式/校验不全（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q193 · [L495](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:495) | GET /admin/exports/{id}；进度及授权下载路径。 | **PARTIAL** | 原生 router:205 有教师授权的按文件名下载；无持久任务/进度/幂等生成状态（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q194 · [L496](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:496) | GET /admin/audit；决策、额度、导入、重置、导出、暂停历史。 | **PARTIAL** | 有 audit 查询；无完整筛选/分页，缺失业务流程没有对应完整审计（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q195 · [L497](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:497) | GET /admin/health；审批链、身份层、队列、磁盘、数据库、备份状态，不输出上游密钥。 | **FAIL** | health 仅局部状态/quick_check，不能证明审批、会话、磁盘、备份、执行器有效（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |

## E4. 内部服务 API

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q196 · [L519](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:519) | POST /requests；可信适配层提交已验证身份、操作、附件和完整快照；完成额度预留。 | **FAIL** | 未实现内部 requests 提交；原生桥接直接操作另一 Service（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q197 · [L520](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:520) | GET /requests/{id}/events；Pipe 获取状态/回答事件，支持 seq；不能改变批准内容。 | **FAIL** | 没有内部事件 API，Pipe 直接访问本地 Service（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)）。 |
| Q198 · [L521](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:521) | POST /requests/{id}/consumer-heartbeat；消费实例、关联会话与租约，识别 WebUI 重启。 | **FAIL** | 无 consumer-heartbeat 端点/生产调用（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q199 · [L522](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:522) | POST /requests/{id}/stop；适配层提交经过验证的取消来源与用户动作。 | **FAIL** | 无认证内部 stop 协议，真实停止未接（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q200 · [L523](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:523) | POST /identities/session-issued；原生成功登录事件登记会话指纹及安全版本；防止伪造重放。 | **FAIL** | 无 session-issued 端点/原生成功登录 hook（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q201 · [L524](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:524) | POST /identities/security-operation；导入、首次改密、重置、安全状态迁移的幂等记录。 | **FAIL** | 无 security-operation 协议/幂等生命周期（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q202 · [L525](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:525) | GET /readiness；供启动器检查；包含协议版本、实例 ID 和保护状态。 | **PARTIAL** | HMAC readiness 端点存在；报告不含真实链路验证且无完整桥接（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |

## E5. 对现有入口的调整

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q203 · [L533](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:533) | `/api/requests` 和旧 `/api/requests/{id}/decision`：取消匿名行为；迁移为内部协议或返回受控迁移错误。不能留下兼容匿名后门。 | **PARTIAL** | 新版服务不暴露旧匿名决策路径；旧 review_service.py/review.html 仍留包内，替代协议未全实现（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q204 · [L534](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:534) | `/api/chat/completions`、`/api/v1/chat/completions`：完整认证、单模型、操作键和 Pipe 白名单；兼容入口不能绕过。 | **FAIL** | 实际中间件把正常聊天统一拒绝，未形成可用受管入口（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)）。 |
| Q205 · [L535](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:535) | `/openai/*`、`/ollama/*`、Anthropic messages、embeddings、音频、图像、tasks、自动摘要、工具/自动化相关入口：按实际路由清单拒绝学生不需要的生成能力。错误返回本地，不尝试上游。 | **FAIL** | 实际路由表遗漏 messages/embeddings，原生上传可触发副处理（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q206 · [L536](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:536) | 原生 functions/models/configs 管理入口继续只允许教师；普通用户工具、插件及提供商设置不开放。 | **FAIL** | 管理路径连教师也被无角色 middleware 封锁（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)）。 |
| Q207 · [L537](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:537) | 原生登录、改密、管理员重置接口必须接入会话登记/撤销流程；不能只保护自建账号页。 | **FAIL** | 原生认证端点没有课堂会话生命周期 hook（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q208 · [L538](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:538) | 原生 task stop 与 WebSocket：同样绑定课堂安全会话和真实停止来源；REST 已拦截但 WebSocket 未处理不算完成。 | **FAIL** | websocket scope 无条件放行，task stop 无关联（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q209 · [L539](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:539) | 健康检查不能是防护豁免生成通道。升级新增路由默认关闭其学生模型能力，直到兼容矩阵验证。 | **FAIL** | 永久 localhost 引导豁免覆盖模型路径，自检/未知版本保护不足（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |

## F1. 审核队列

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q210 · [L547](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:547) | 每条显示名册名、登录标识、提交时间、等待时间、当前模型、附件数量及预留状态。 | **PARTIAL** | 列表有 user_id/时间/消息；缺名册名、等待时间、模型附件/预留完整展示（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q211 · [L548](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:548) | 当前文字直接展示；图片缩略图可放大查看实际送模版本；文本文件可看全文和行号，可下载原件。 | **FAIL** | 无真实图片预览、代码全文/行号或原件下载（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q212 · [L549](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:549) | 可展开完整上下文和教师改写前后差异；教师批准的是这份有效快照。 | **PARTIAL** | 显示消息 JSON；没有权威上下文构造和编辑差异/内容审阅（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q213 · [L550](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:550) | 单条通过、修改后通过、拒绝；拒绝原因可填，界面明确“拒绝也使用 1 次”。 | **PARTIAL** | 单条批准/拒绝存在；无修改后批准 UI，实际页面 API 不通（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q214 · [L551](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:551) | 复选框、全选当前待审、批量通过/拒绝；显示选中人数及扣次影响，不默认选中全部。 | **FAIL** | 无请求复选、全选、批量通过/拒绝（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q215 · [L552](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:552) | 取消对话框真正取消；按钮提交中禁用；网络不明时先查原操作结果，不立刻重发新的决定。 | **PARTIAL** | prompt 取消能返回；按钮提交保护/未知结果查询不足（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q216 · [L553](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:553) | 过期项自动从待审移除，在历史可查“跨日过期，0 次”。显示教师时区。 | **FAIL** | 没有自动到期生命周期和教师时区展示（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q217 · [L554](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:554) | 教师修改问题不另建一个收费请求；学生会看到教师修改提示。 | **PARTIAL** | 核心 edit 不新增收费请求；学生原始/修改版本呈现和后续上下文未完成（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |

## F2. 学生额度

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q218 · [L560](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:560) | 单人 +1/-1；选择多个或全班后 +1/-1/自定义增减。 | **PARTIAL** | 有选中学生 +/-1；缺完整单人、全班全选和自定义增减（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q219 · [L561](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:561) | 操作前预览每人的变化，提交后展示明确结果和历史入口。 | **PARTIAL** | 调用预览但不保留版本/日期，响应与历史入口不足（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q220 · [L562](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:562) | 减次数不能使已预留问题消失或把可用变负。 | **PASS** | 底层调整事务禁止 available<0，不删除已预留问题，测试通过。 |
| Q221 · [L563](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:563) | 重置密码、单人暂停放在学生操作菜单。教师重置密码显示“下次登录需改密，旧会话已撤销”且后端真实执行。 | **PARTIAL** | 有密码重置动作但撤销未可靠执行；单人暂停菜单缺失（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q222 · [L564](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:564) | 不提供清空历史或伪造已使用次数的“快捷重置”。 | **PASS** | 未提供清历史/改 used 的快捷清零入口，调整保留 ledger。 |

## F3. 历史与导出

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q223 · [L568](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:568) | 学生、日期、状态过滤；展示原文、教师有效改写、图片/代码附件、完整或中断回答、结算原因、调整与审批人。 | **FAIL** | 无完整历史页及日期/学生/状态联合筛选、原始/有效附件和结算展示（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q224 · [L569](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:569) | 教师可以导出单人、多人和全班；默认 ZIP 内含 JSON（机器可读）、Markdown（教师阅读）、额度/审计 CSV、附件及 manifest 校验清单。 | **PARTIAL** | ZIP 有 JSON/Markdown/CSV/附件/manifest；漏旧聊天、无文件哈希和完整范围选择（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q225 · [L570](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:570) | 使用稳定学生 ID 和安全文件名，避免同名覆盖、路径穿越、CSV 公式执行和 HTML/Markdown 主动脚本。 | **PARTIAL** | 使用稳定 ID/安全文件名与 CSV 转义；Markdown 主动内容在真实浏览器中未验证，不据此宣称已利用。 |
| Q226 · [L571](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:571) | 优先通过原生管理员 API 读取旧聊天；新请求使用课堂不可变归档补足删改、拒绝、过期和中断记录。 | **FAIL** | 没有原生管理员聊天读取/legacy 适配（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q227 · [L572](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:572) | 导出不包含密码、会话令牌、提供商 Key、服务签名密钥或敏感配置。只导出可展示模型输出，不把内部诊断/隐藏推理当课堂回答。 | **PARTIAL** | 新课堂导出不主动读取密码/Key；完整数据来源、隐藏内容隔离及原生合并导出尚缺（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q228 · [L573](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:573) | 永久留存下 UI 必须分页/流式导出，不能永远依赖一次性 /chats/all/db 读全部进内存。 | **FAIL** | 先分页读后累积所有请求入内存，不是真正流式导出；实际查询无 cursor（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |

## G1. 登录、次数、状态和恢复

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q229 · [L579](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:579) | 成功使用初始密码登录后立即进入首次改密页面；改密完成前不能聊天、上传文件或调用其他受保护功能。 | **FAIL** | 原生首次登录不重定向/限制，课堂上传在必改状态也可用（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q230 · [L580](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:580) | 输入框附近持续显示“今日可用 N 次 / 预留 M 次”；拒绝也扣次的规则在首次使用和提交状态中明确可见。 | **PARTIAL** | 自建页显示可用/预留；未集成原生输入区，实际路径/刷新联动失败（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q231 · [L581](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:581) | 显示待审、批准排队、生成、拒绝、过期和意外中断；不能只显示永久旋转图标。 | **PARTIAL** | 部分状态轮询呈现；批准任务不执行，不能形成可用闭环（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q232 · [L582](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:582) | 有待审取消和生成停止；点击停止时根据是否已有回答明确其扣次影响。 | **PARTIAL** | 取消按钮存在；交付语义/真实停止和清楚扣次影响未完整实现（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q233 · [L583](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:583) | 请求去重、限额与必改密均在后端执行。禁用按钮只是辅助。 | **PARTIAL** | 核心额度与活动限制有效；原生会话/必改和绕过边界失败（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q234 · [L584](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:584) | 失败/拒绝可编辑后重新提交；这是新操作，重新审批。失败的旧操作不扣；拒绝的旧操作已扣且不自动恢复。 | **PARTIAL** | 可新操作再提问；缺明确重试恢复，错误流可能已错误收费（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q235 · [L585](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:585) | 刷新后恢复活动请求、已归档回答和 quota；同一个问题不能因刷新生成两次。 | **FAIL** | 只查询 pending 活动，排队/生成刷新不恢复，操作 key 未持久化（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)、[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)）。 |
| Q236 · [L586](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:586) | 已经被教师修改的问题须显示原始提问与“教师调整后提交”的版本，后续上下文使用有效版本。 | **FAIL** | 页面无完整改写前后历史，后续上下文未重建（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q237 · [L587](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:587) | 禁止学生临时会话、导入任意聊天历史及物理删除服务器留存；可以隐藏/归档自己的会话。若原生删除仍开放，独立课堂归档必须不受影响。 | **PARTIAL** | 新课堂归档独立于原生删除；旧聊天和正常会话完整留存未接通（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |

## G2. 图片与文本类附件

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q238 · [L595](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:595) | 图片；PNG、JPEG、WebP；每张 <= 5 MiB，解码后 <= 20 百万像素；服务端校验真实格式和尺寸，生成安全预览。 | **PARTIAL** | 5 MiB/20M 像素头部限制存在；无真实安全解码/预览，常见 WebP 被拒（[M01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M01)）。 |
| Q239 · [L596](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:596) | 文本与代码；.py、.txt、.md、.csv、.json、.yaml、.yml、.log；每份 <= 1 MiB；UTF-8/UTF-8 BOM 优先，失败时可显式选择 GB18030；不静默乱码替换。 | **PASS** | 支持计划文本扩展名、1 MiB、UTF-8/BOM 与显式 GB18030；本地文本读取，不执行代码。 |
| Q240 · [L597](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:597) | 总量；每请求最多 5 份附件，总计 <= 10 MiB；文本注入还受模型上下文预算约束。 | **PARTIAL** | 核心最多 5 份/10 MiB；UI 单文件、上下文预算没有检查（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q241 · [L598](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:598) | 暂不支持；可执行文件、压缩包、宏、Office、扫描 PDF、音视频、Notebook 执行、外部 URL 文件抓取。拒绝并给出支持格式说明。 | **PASS** | 本地附件白名单拒绝非支持类型/外部 URL，不主动增加 OCR/RAG/执行能力；原生旁路另见 [C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)。 |
| Q242 · [L604](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:604) | 文件先在本地完成大小、格式、所有权和实际 SHA256 校验；不信任上传元数据里的 file_hash。 | **PARTIAL** | 本地所有权、大小、实算 hash 有验证；图片格式只看头部（[M01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M01)）。 |
| Q243 · [L605](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:605) | 原生 `/files/?process=false` 可复用存储，必须由服务端强制这一模式；学生不能改回 process=true 绕到 RAG/嵌入。适配上传与后续状态 UI，避免原生等待永远不会发生的向量化。 | **FAIL** | 没有强制原生 process=false 或文件状态适配（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q244 · [L606](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:606) | 源文件复制为课堂不可变附件；教师预览、模型输入和导出引用同一规范化字节版本。原生附件被编辑/删除也不能变更已批准请求。 | **PARTIAL** | 课堂 blob/hash 不变核心已测；原生 file adapter 和教师实际字节预览缺失（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q245 · [L607](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:607) | 文本直接在本地提取并带文件名边界注入上下文；不执行 .py，不启用代码解释器，不联网下载模型来读取文本。 | **PASS** | .py 只经文本解码与带边界注入，没有执行该文件或外部解析。 |
| Q246 · [L608](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:608) | 图像使用服务保存的实际图像内容传给具备图像能力的上游；纯图片问题也生成待审请求。 | **PARTIAL** | 本地图片可入快照；缺模型图像能力、原生接入，纯图 UI 不能提交（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q247 · [L609](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:609) | 禁止任意 file://、网络 URL、localhost URL 与任意磁盘路径输入；已有图片 data URI 也必须解码、限制体积并归档。不得允许用户让后端任意抓取内网资源。 | **PARTIAL** | 核心拒绝外部/file URL 与附件越权；原生接入和总请求体边界未完整验证（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q248 · [L610](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:610) | 模型不支持图像时在预留/审批前报清楚；不能丢掉图片只传文字，也不能审批后默默换模型。 | **FAIL** | 没有真实模型图像能力预检（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q249 · [L611](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:611) | 超过模型上下文时明确拒绝或让学生精简。禁用自动 AI 摘要；如需确定性裁剪历史，应在教师看到的快照中明示裁剪范围，批准后不可再变。 | **FAIL** | 没有模型上下文预算/确定性裁剪展示，历史权威构建缺失（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q250 · [L612](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:612) | 教师文字改写不得把多模态 content 列表整体替换成字符串而丢附件。 | **PARTIAL** | 核心 edit 保留附件已有测试；教师 UI 不能编辑且原生多模态未接（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q251 · [L613](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:613) | 本版本插件加载器返回 Filter 实例：`OWUI/utils/plugin.py:298—300`，消费端读取 `function_module.file_handler`：`utils/filter.py:185`。因此不能照抄最新版文档“只设模块级 file_handler”的示例；对当前 0.11.2 实际实例属性行为写集成测试。文件引用被清理前必须保存可信关联供 Pipe 使用，不能清空后让附件消失。 | **FAIL** | Filter 无实例 file_handler，bootstrap 未安装，Pipe 忽略 __files__（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q252 · [L614](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:614) | 所有自动摘要、历史压缩、搜索、embedding、文件上传处理发生在 Pipe 前的可能路径都纳入 E5 防护清单，不把“用了 Pipe”误认为这些调用已自动覆盖。 | **FAIL** | 未覆盖全部 Pipe 前副调用入口；不能把 Pipe 文件存在算作防护（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |

## H2. 原生 API 与扩展的优先级

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q253 · [L674](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:674) | 使用官方 Pipe / Filter 注册 API，校验 installed content hash、is_active、模型可用性和函数签名。 | **PARTIAL** | bootstrap 调用官方 Function API；签名/installed content 真 hash/模型有效性未实测，ID 不一致（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q254 · [L675](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:675) | 用户创建、改密、角色、文件所有权和旧聊天读取调用原生 API/官方业务处理器，不通过手写 SQL 修改第三方 auth/user/chat。 | **PARTIAL** | 账号 API 复用而非写第三方哈希；文件所有权、原生聊天读取未实现（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q255 · [L676](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:676) | 内部 imports 限制在 native_api.py 等版本适配层；对其行为写准确版本契约测试。其他业务代码不散落第三方私有 imports。 | **FAIL** | native_api.py 无运行调用，真实私有 imports/认证实现散落且准确版本端到端契约缺失（[L02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L02)）。 |
| Q256 · [L677](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:677) | 原生插件不是完整认证中间件。first-password、会话撤销、禁止旁路入口要在 ASGI 适配层或最小明确源码补丁中完成。 | **FAIL** | ASGI middleware 不覆盖会话、首次改密、WS 与完整出口（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q257 · [L678](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:678) | 如果 UI 没有足够的官方扩展点，维护可重放、校验基准哈希的小补丁；修改官方对应 tag 的源码后构建前端。不能把 Sub2API frontend 当成 Open WebUI 前端，也不能直接搜改打包 JS。 | **PARTIAL** | 没有搜改压缩 JS/误改 Sub2API；必要前端操作标识、改密和停止适配也未完成（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q258 · [L679](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:679) | 每个补丁记录 upstream tag、commit/文件哈希、原因、测试和撤销条件。拒绝“任何版本尽量注入成功”；未知版本启动为维护状态。 | **FAIL** | 没有经验证的补丁/运行版本拒绝机制；静态兼容 JSON 不证明运行条件（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q259 · [L680](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:680) | 教师管理模型的实际提供商配置移到课堂设置，Open WebUI 只暴露受管 Pipe。旧外部连接在成功迁移后关闭并从普通提供商配置移除真实 Key；用户角色和 API Key 权限不作为唯一隔离手段。 | **FAIL** | 未迁移/移除原生可达提供商密钥，没有课堂配置与统一出口（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q260 · [L681](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:681) | 禁用原生对学生开放的 workspace tools、direct connections、额外 Functions、API key 建立和不需要的生成特性；E5 的后端约束仍不可省略。 | **PARTIAL** | 部分前缀和配置设置存在；实际副入口/上传/持久注册配置仍未关闭验证（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## 原生成功登录

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q261 · [L689](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:689) | 由当前版本原生认证校验 email/password 和账号角色。 | **PARTIAL** | 继续依赖原生认证；课堂登录后处理未挂接（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q262 · [L690](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:690) | 适配层只捕获明确成功的服务端登录结果，验证其 user_id，登记返回 JWT 指纹、当前 auth_epoch、有效期。 | **FAIL** | 无成功登录事件捕获，首次访问任意旧 JWT 即自动登记（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q263 · [L691](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:691) | 启用 must_change_password 的学生仅可访问自身会话信息、改密、退出和必要静态资源；不能访问聊天、附件、模型、副接口或建立有权执行的 WebSocket。 | **FAIL** | 必改学生可上传，原生受保护 REST/WS 无统一限制（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q264 · [L692](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:692) | 普通学生需要 active enrollment + 当前 epoch 的登记会话。未登记的历史 JWT 一律要求重新登录。 | **FAIL** | 虽然有 enrollment 检查，未登记旧 JWT 可重新进入当前 epoch（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q265 · [L693](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:693) | 所有 API/WS 请求同时通过原生角色检查和课堂安全状态；服务不可用时默认拒绝，不能退回纯原生认证继续用 AI。 | **FAIL** | 没有所有 REST/WS 的课堂安全检查/服务失联默认拒绝（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |

## 批量导入与初始密码

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q266 · [L699](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:699) | 按原生 API 创建 role=pending 的账号作为安全过渡，避免两个数据库写入之间学生已可使用。 | **FAIL** | 原生创建直接 role=user，没有 pending 过渡（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q267 · [L700](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:700) | 建立 students/enrollment 与 security_states，设置 must_change_password=true。 | **PARTIAL** | enroll 与必改状态能写入；在原生创建之后才执行，存在崩溃窗口（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q268 · [L701](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:701) | 成功后原生角色改为 user，enrollment active。初始密码登录只可改密。 | **FAIL** | 无 pending→user 的安全完成协议，user 在状态建立前已生效（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q269 · [L702](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:702) | 创建成功而第二步失败时维持 pending/provisioning，教师在导入报告中可恢复；不能为了“全部成功”临时放开所有 user。 | **FAIL** | 无持久安全过渡/跨重启接续，补偿和重放不可靠（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q270 · [L703](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:703) | 学生改密必须验证旧密码，新密码不可等于初始/当前密码；经原生改密成功后才更新状态、增加 epoch、撤销旧会话。 | **FAIL** | 实际 native first-password 未检查新旧不同、未验证原生 bool 成功（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q271 · [L704](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:704) | 完成后要求重新登录，避免同秒 iat 与撤销时间造成边界漏洞；新会话只有成功登录才登记。 | **PARTIAL** | 接口有重新登录提示；旧会话/原生登录登记并未可靠执行（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q272 · [L705](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:705) | 改密途中崩溃默认仍为必改/受限状态，通过教师重置恢复。不得在原生改密前先清除强制标志。 | **PARTIAL** | 不是提前清必改标志，但原生 200 false 被当成功，安全操作状态/恢复缺失（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |

## 教师重置密码

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q273 · [L709](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:709) | 在课堂数据库事务中设 reset_in_progress、must_change_password=true、auth_epoch+1，立即阻断旧会话。 | **FAIL** | 实际先调用原生密码更新，未先锁定/提升 epoch（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q274 · [L710](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:710) | 调用原生管理员重置 API。 | **PARTIAL** | 会调用原生管理员 API；成功结果、安全顺序和失败恢复不完整（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q275 · [L711](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:711) | 成功后完成安全状态并保留必改；失败保持安全封锁并向教师提供幂等恢复操作。 | **FAIL** | 没有 reset_failed 封锁及幂等恢复流程（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q276 · [L712](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:712) | 捕获原生管理界面直接重置的同等事件，不能只覆盖课堂重置按钮。正常学生改密也应撤销已有会话。 | **FAIL** | 原生管理重置和正常改密没有课堂 hook（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q277 · [L713](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:713) | 不把原生成功 JWT 的旧签发时间与客户端提供时间简单比较；使用服务端记录的 epoch/令牌指纹。 | **PARTIAL** | 自有会话使用指纹/epoch；原生旧令牌懒登记破坏代次保护（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q278 · [L714](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:714) | 注册、被删后重建、角色变化、登出、所有会话注销、教师登录也纳入契约测试。 | **NOT VERIFIED** | 没有注册/删重建/角色变化/登出/教师登录的完整准确版本契约测试；已知原生 hook 缺陷见 [H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)。 |
| Q279 · [L715](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:715) | 完整权限的教师仍可以维护账号；紧急恢复走本机管理员维护工具，在学生入口关闭时执行并留审计，不暴露远程匿名恢复路由。 | **FAIL** | 没有完成受控本机账号安全恢复工具，教师部分管理入口反被封锁（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |

## H4. 账号名册导入

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q280 · [L726](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:726) | 必须用标准 CSV 解析器，支持 BOM、引号和逗号；不依赖原生前端的简单 split。 | **PASS** | 采用标准 csv.DictReader 和 BOM 处理；引号/逗号及 admin 注入相关测试通过。 |
| Q281 · [L727](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:727) | 接受原生四列；用户另提供 Name,Username,Password 时，预览中显式把简单标识映射为 `username@classroom.local`，显示最终登录账号，禁止静默改变用户已有合法邮箱。 | **PASS** | Name/Username/Password 可显式映射 classroom.local，预览保留合法 Email。 |
| Q282 · [L728](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:728) | 没有自动生成姓名/学号的硬规则。批次内重复、系统已有同邮箱、大小写冲突、非法角色、缺列、空密码和非法编码都必须报告。 | **PARTIAL** | 有多项逐行校验；未完整查询原生既有邮箱冲突，全无效批次结果丢行（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q283 · [L729](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:729) | 角色固定学生 user；来自文件的 admin 不得按文件执行。原生过渡创建用 pending 是内部安全步骤。 | **PARTIAL** | 拒绝 CSV admin 已测；原生创建应 pending 的阶段未实现（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q284 · [L730](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:730) | 已存在账号默认不覆盖姓名/密码；预览显示冲突或明确关联已有 user，关联操作需要教师明确提交，不能顺便重置其他人。 | **PARTIAL** | 不直接覆写现有账号密码；原生冲突预览/明确关联与接管流程缺失（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q285 · [L731](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:731) | 导入可以逐行成功，因为原生 API 不是跨所有账号的单事务。必须有逐行持久结果、重复批次恢复和部分失败报告，不声称“全班原子建号”。 | **FAIL** | 跨重启无法恢复内存预览，已完成批次重放也报错（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q286 · [L732](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:732) | 并行建号初始限制为 2—4，避免密码哈希瞬时占满教师机；30 人无须追求高吞吐。 | **PASS** | 当前顺序建号避免密码哈希并发压力；采用更保守并发 1 可接受，30 人时延未实测。 |
| Q287 · [L733](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:733) | 教师可下载一次性账号初始密码清单；不能提供查询当前密码功能。导入文件不进入普通日志、持久导入表或历史导出。 | **PARTIAL** | 未保存密码在持久表/普通导出；缺一次性初始密码下载流程（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q288 · [L734](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:734) | 原生手动创建的学生也必须通过 enrollment 和初始改密流程才能用课堂模型。教师可在课堂面板“接管已有账号”，不会因原生新增路径遗漏而免改密。 | **FAIL** | 没有教师接管已有原生账号/enrollment+必改的完整接口（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q289 · [L735](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:735) | 禁止公开自助注册；实际数据库中的持久配置也要更新并读取验证，不能只设置同名环境变量。 | **FAIL** | 未完成持久配置关闭注册并读回验证；现有库仍 true（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## I1. 包装与配置

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q290 · [L741](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:741) | 保持 Windows x64、相对目录启动；程序可解压到带中文和空格的普通本地路径。 | **FAIL** | 完整 launcher 模块搜索路径失败，含空格路径参数也失败（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)、[H19](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H19)）。 |
| Q291 · [L742](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:742) | 常用入口不依赖系统 Python、Docker、Node、pip 联网、用户 PATH 或原开发 E 盘。 | **PARTIAL** | 已提供便携解释器入口；完整启动/最终包未成功，不能靠开发 Python 证明（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q292 · [L743](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:743) | 当前已有 fastapi、uvicorn、httpx、pydantic、Pillow、tzlocal、tzdata 等依赖，优先复用。升级任何库先检查 Open WebUI 锁定要求，不盲目 pip install -U。 | **PASS** | 主要复用现有运行库，没有无理由升级；已核对声明的少量 pin 与当前安装版本。 |
| Q293 · [L744](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:744) | 运行锁定文件包含准确版本与可获得的安装包哈希；建包在干净阶段安装/复制依赖并检查；不可依赖当前机器碰巧有某个 DLL/模块。 | **FAIL** | 锁文件没有 wheel 哈希与完整传递组件清单，无干净构建验证（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q294 · [L745](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:745) | 配置统一为一个非秘密文件，含数据根目录、端口、时区检测、并发、超时、上传限制和保护版本；密钥另存。 | **FAIL** | 无统一非秘密配置文件；DataRoot/端口/时限/模型配置分散（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q295 · [L746](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:746) | 内部端口默认 8790，公开 3000；学生/教师同源访问。继续仅向域/专用网络的 LocalSubnet 开放公开端口。 | **PARTIAL** | 默认 3000/127.0.0.1:8790；防火墙规则缺 LocalSubnet，课堂路由失败（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q296 · [L747](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:747) | LAN HTTP 会明文传输认证信息。首版在受控课堂局域网部署，文档明确边界；不得以“本地网络”声称已加密。需要 HTTPS 时提供受信任证书配置，不把未配置 TLS 的承诺写入验收。 | **PARTIAL** | 保留受控 LAN HTTP 的部署边界；页面 randomUUID 不兼容默认 HTTP，TLS/实际学生浏览器未验（[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)）。 |
| Q297 · [L748](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:748) | 不信任任意 X-Forwarded-For；没有代理则不设 forwarded_allow_ips='*'。身份与额度不使用 IP。 | **PASS** | 没有发现新增 forwarded_allow_ips='*'；核心身份/额度按可信 user_id，不使用 IP。 |
| Q298 · [L749](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:749) | 运行数据保存在 data，日志不打印原文/初始密码/Key；完整问题只保存在受保护归档。 | **PARTIAL** | 新脚本不打印初始密码/Key、课堂归档本地保存；打包筛选与磁盘管理不足（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q299 · [L750](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:750) | 教师使用说明更新模型设置位置、首次改密、拒绝扣次、过期保留、单独/批量调整、导出和故障处理。 | **PARTIAL** | 新增中文指南覆盖主题；多项功能/命令实际不匹配，原包旧指南未替换（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |

## I2. 启动与关闭

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q300 · [L754](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:754) | 取得实例锁，校验配置、路径、磁盘空间、依赖、版本哈希、端口归属。 | **FAIL** | 缺实例锁/磁盘/完整依赖版本/端口归属校验（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q301 · [L755](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:755) | 准备安装独有密钥；首次管理员在学生入口可访问前创建，关闭公开注册。 | **PARTIAL** | 有安装密钥和首次初始化意图；全链实际启动、持久注册关闭未通过（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q302 · [L756](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:756) | 完成/验证自有与原生迁移；失败进入维护状态，不能继续启动模型访问。 | **PARTIAL** | 原生迁移未证实则 launcher 拒启是合理保护；自有 VerifyOnly 写库/完整迁移尚缺（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[M05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M05)）。 |
| Q303 · [L757](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:757) | 启动课堂服务和受保护的 Open WebUI，安装 Pipe/Filter/适配层。 | **FAIL** | 完整启动有模块导入和页面布局/挂载缺陷，保护与 worker 未接（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)—[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q304 · [L758](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:758) | 真实 readiness 校验：数据库可用、会话防护有效、只有受管模型可用、匿名决策失败、非受管模型出口失败、生成任务可关联、文件处理不执行 RAG。 | **FAIL** | readiness 未验证真实会话、出口、执行、文件处理（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q305 · [L759](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:759) | 本地模型连通性测试可以由教师显式启动；普通启动自检使用模拟/非生成检查，不自动消耗上游费用。 | **PARTIAL** | 普通启动未主动做付费生成；教师显式受管测试功能缺失（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q306 · [L760](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:760) | readiness 成功后开放学生使用，再显示教师/学生地址。双击重复启动只打开已验证的本实例，不把任意 /health=200 的其他程序当本服务。 | **FAIL** | 现有 service PID/任意 ready health 可让 Start 提前退出，无真正实例验证（[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q307 · [L761](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:761) | 单个服务崩溃可恢复对应服务；先关闭学生新请求，避免“半启动”永久报端口占用。 | **FAIL** | 半启动时不能可靠恢复另一个服务（[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q308 · [L762](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:762) | 停止：暂停新提交/派发，等待短暂排空；超时教师选择停止或后台默认安全终止，将未完成生成记零次故障；持久化、关闭数据库和网络。 | **FAIL** | Stop 直接终止，无暂停/排空/真实停止/运行恢复结算（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q309 · [L763](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:763) | PID 校验可执行路径、命令行和实例 ID 后才能 Stop-Process。Start/Stop/Status/Backup 统一 DataRoot。 | **PARTIAL** | 部分可执行路径/时间检查；缺命令行/实例 ID，DataRoot 不统一，失败仍删 PID（[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q310 · [L764](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:764) | 服务每次重启使用新的 worker_instance_id；旧 claim 不可延续成第二次模型调用。 | **PARTIAL** | Service 实例会生成新 worker ID；旧 claim 恢复未自动处理（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |

## I3. 备份与长期留存

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q311 · [L768](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:768) | 自动备份建议每天第一次成功启动时做一次，另提供教师一键备份。备份本身可以有轮转保留策略，但不能轮转删除唯一的业务历史。 | **PARTIAL** | 有手工备份脚本；无每日首启动自动备份，默认同名文件缺原子发布（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q312 · [L769](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:769) | 备份同时包含 Open WebUI DB、课堂 DB、已引用的上传/附件/回答归档、非秘密配置、迁移/协议版本和文件清单。 | **FAIL** | 备份不包含原生账号/聊天库、原生上传及完整配置（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q313 · [L770](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:770) | 采用维护暂停 + SQLite Backup API/可靠 checkpoint + 一致文件清单；禁止只拷贝正在写入的 .db 而漏 WAL/附件。 | **PARTIAL** | 使用 SQLite Backup API；没有联合维护屏障和完整文件引用清单（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q314 · [L771](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:771) | 两个数据库和文件引用应标注同一 backup_id/维护屏障，验证引用完整。 | **FAIL** | 无两个库与文件统一 backup_id/屏障和引用校验（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q315 · [L772](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:772) | 密钥的迁移与恢复单列说明；机器绑定 DPAPI 不能跨机直接用，应在新机重新配置提供商密钥，并轮换实例内部认证密钥。 | **PARTIAL** | 有密钥重配的方向说明；尚无完整受管密钥迁移/新实例验证流程（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q316 · [L773](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:773) | Restore 默认恢复到新目录，校验清单、版本、数据库完整性、文件哈希，再切换启动配置。不得在未验证时覆盖唯一原数据。 | **FAIL** | 先覆盖目标后验证哈希，坏备份可毁原文件（[H18](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H18)）。 |
| Q317 · [L774](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:774) | 永久图片归档可能远大于聊天文字，30 人也需要磁盘容量显示与低空间暂停上传/派发；不自行删旧聊天“腾空间”。 | **FAIL** | 无磁盘容量显示或低空间暂停（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q318 · [L775](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:775) | 学生退学/账号删除仅停止访问；历史依然按用户确认永久保留。教师导出保留原稳定身份。 | **PARTIAL** | 新课堂身份/记录未被原生级联删除；完整旧数据与删除事件适配未完成（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q319 · [L776](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:776) | 导出的 ZIP 是阅读/分析交付，不自动当作可恢复全系统备份；两者格式和用途明确区分。 | **PASS** | 提供了独立导出和备份入口，二者用途不同；当前备份完整性失败另见 [H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)。 |

## J1. 迁移前保护

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q320 · [L782](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:782) | 记录旧包校验值、版本、当前服务实例、数据库计数、表结构与文件清单；不要在报告中放密码或 Key。 | **PARTIAL** | baseline manifest 记录部分自有文件 hash；无完整源码快照/数据与文件基线及验证恢复（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q321 · [L783](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:783) | 暂停学生访问，正常停止旧服务，创建经过恢复验证的完整备份。 | **FAIL** | 没有经过恢复验证的完整备份和可用维护切换流程（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)、[H18](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H18)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q322 · [L784](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:784) | 所有首次迁移在独立副本执行；保留原目录只读作为回滚基线。 | **PARTIAL** | 结构清单工具只读分析、不直接改现有库；完整隔离迁移/回滚副本演练未实施（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q323 · [L785](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:785) | 不把当前使用中的 data、logs、teacher-admin.json 或 .webui_secret_key 装入面向其他电脑的全新发行 ZIP。 | **FAIL** | 新 Build-Package 无正向清单，运行后源码目录 data/logs 可入 ZIP（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## J2. 修正原生迁移基线

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q324 · [L791](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:791) | 锁定 Open WebUI 0.11.2 的完整 schema、迁移脚本及基准哈希。 | **PARTIAL** | 声明版本 0.11.2 并有 schema 清单工具；没有锁定官方迁移生成库及完整基准 hash（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q325 · [L792](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:792) | 比对当前库与该版本官方迁移生成的干净库：列、索引、外键、唯一性、默认值及历史数据转换。 | **PARTIAL** | 能比较部分结构清单；没有证明官方干净迁移库与当前历史数据转换等价（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q326 · [L793](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:793) | 对副本检查重复邮箱及一致性；不能为了创建索引擅自删除或合并账号。 | **NOT VERIFIED** | 未在完整隔离历史数据副本上执行并留存重复邮箱/一致性验证报告。 |
| Q327 · [L794](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:794) | 推荐产生明确的基线修复迁移，补齐已验证缺口；只有结构及必要数据转换完全等价后，才登记正确迁移 revision。 | **FAIL** | 无经验证的基线修复迁移，verified 只是手工环境标记（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q328 · [L795](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:795) | 如果无法证明等价，改用官方流程建立新库，再通过受控迁移适配保留原 user_id、聊天与关系；不得重新 signup 后把旧数据硬挂到新随机用户。 | **FAIL** | 没有等价失败时保留 user_id/关系的受控迁移适配（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q329 · [L796](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:796) | 精确报告执行了哪些迁移、哪些是已证明无需执行；不能无条件 stamp head，也不能直接启动一串会 CREATE 已有表的历史迁移。 | **PARTIAL** | 没有无条件 stamp head，文档明确未完成；也没有实际迁移/跳过依据报告（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q330 · [L797](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:797) | 验证登录、创建用户、聊天、文件、Functions、导出后再进入业务迁移。 | **NOT VERIFIED** | 没有迁移后登录/建号/聊天/文件/Functions/导出的准确版本联合验收。 |

## J3. 课堂数据

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q331 · [L801](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:801) | 导入现有普通用户到 students，保留 user_id；教师管理员保留权限。 | **FAIL** | 未提供迁移旧用户/enrollment 的脚本或实际记录（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q332 · [L802](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:802) | 现有学生首次进入新系统也要求改密；迁移后所有旧课堂会话要求重新登录。 | **FAIL** | 现有学生必改/旧会话迁移未实现，原生 hook 本身也缺失（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q333 · [L803](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:803) | 旧 review_requests 的原 ID、key、姓名/邮箱快照、原文、教师改写、决定时间和状态原样保存在 legacy 记录或兼容列。 | **FAIL** | legacy 列空壳，无旧请求/改写/决策历史导入器（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q334 · [L804](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:804) | 旧 approved 不证明模型成功，不转成可重用授权，也不追扣今天次数。 | **PARTIAL** | 未发现把旧 approved 转授权/追扣的实现；但整个旧数据迁移未做，不能标 PASS（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q335 · [L805](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:805) | 旧 pending 没有可靠完整快照和执行关联：保留历史，标记“迁移关闭，需重新提交”，不自动批准/发送、不扣次数。 | **FAIL** | 无旧 pending 迁移关闭/保留流程（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q336 · [L806](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:806) | 旧普通聊天继续可查看与导出；继续旧聊天时，将完整上下文作为新的教师可审快照，不能把来源未验证的旧内容直接当成已批准上下文。 | **FAIL** | 没有旧原生聊天导出和续聊上下文适配（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)、[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q337 · [L807](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:807) | 新额度从切换日开始。不得由旧 approved/rejected 记录推断过去的准确使用次数；导出标记 legacy_usage_unknown。 | **PARTIAL** | 新日桶不推算旧使用；切换日/legacy_usage_unknown 标注和迁移报告缺失（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q338 · [L808](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:808) | 旧本地教师明文密码文件和含密码日志在确认不再被启动依赖后，迁移为受限备份或提示教师处理；不在代码任务中未经计划直接删除唯一恢复信息。 | **NOT VERIFIED** | 未执行旧密码文件/日志的受限迁移，原文件未被本次审计触碰；完整迁移步骤待验证。 |
| Q339 · [L809](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:809) | 上游配置复制进新服务凭据存储并测试映射。确认唯一出口生效后关闭原生真实提供商路径，保留可回滚的加密/受限备份。 | **FAIL** | 提供商凭据/映射迁移和旧出口关闭未实现（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## J4. 切换与回滚

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q340 · [L813](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:813) | 副本验收通过后，使用同一已验证迁移脚本在维护窗口切换；核对用户/聊天/附件/旧审批数量与哈希。 | **FAIL** | 没有通过验收的统一切换脚本与迁移数量/hash 对账（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q341 · [L814](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:814) | 保留旧数据与新版数据分别可识别，禁止用旧服务直接打开已升级不可逆的新库。 | **PARTIAL** | 新课堂库独立，保留旧库；原生升级、目录版本和禁止不兼容旧服务的完整切换保护未完成（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q342 · [L815](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:815) | 如果新版已发生新对话，回滚不能简单恢复旧备份丢掉新数据；先归档增量并进入维护，采用已验证的降级/数据合并流程。没有兼容降级时明确停留维护，不能假报回滚成功。 | **FAIL** | 无增量归档/兼容降级或停留维护的可执行回滚流程（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q343 · [L816](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:816) | 回滚旧功能也不得重新对学生开放已知无审批旁路。未恢复完整保护前，仅教师维护访问。 | **FAIL** | 尚无经验证的受保护回滚；现有旧出口缺陷不能随回滚开放（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## K1. 额度与时间

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q344 · [L826](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:826) | 新学生当日首次查询；base=3、used=0、reserved=0、available=3；查询不新建多个桶。 | **PASS** | 核心新生日桶 read 已测，base=3/used=0/reserved=0/available=3。 |
| Q345 · [L827](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:827) | 提交第一问；pending、reserved=1、available=2，上游 0。 | **PASS** | 核心提交预留 1、pending、上游 0 已测。 |
| Q346 · [L828](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:828) | 教师拒绝；used=1、reserved=0、available=2，上游仍 0；重复拒绝不重复扣。 | **PASS** | 核心拒绝收费 1、重复不再结算、上游 0 已测。 |
| Q347 · [L829](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:829) | 教师批准并成功；最终 used=1，一次派发；从提交到成功不是扣两次。 | **PARTIAL** | 直接 Worker 正常完成及唯一 claim 已测；真实 API 无运行派发器（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q348 · [L830](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:830) | 同一天三次拒绝；used=3，第四次不能进入队列，不发上游。 | **PASS** | 核心额度耗尽/单活动测试覆盖三次收费后拒绝第四问。 |
| Q349 · [L831](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:831) | 同一天三次成功；同上；追问和重新生成按新问题处理。 | **PARTIAL** | 正常核心成功结算已测；原生追问/重新生成没有完整链（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q350 · [L832](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:832) | 上游报错/网络断开/服务重启；有无部分回答都 charge=0，预留释放，部分输出留存“不完整”。 | **FAIL** | 独立复现真实解析器截断/SSE error/空响应被收费；重启未自动恢复（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q351 · [L833](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:833) | 学生主动停止无正文；charge=0；已有可展示回答后主动停止 charge=1。 | **FAIL** | 持久化未交付仍扣、停止不结束真实执行，存在 claim 竞争（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q352 · [L834](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:834) | 教师停止/暂停维护中止；charge=0，不能记学生主动停止。 | **PARTIAL** | 原生教师 stop 路由和 source 分类存在；实际执行未取消，运维停止未接安全结算（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q353 · [L835](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:835) | 跨日 pending；expired、从待审移除、原日预留释放、历史和附件仍在；新日 base=3。 | **FAIL** | 只运行查询/健康检查时跨日 pending 不会移出（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q354 · [L836](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:836) | 午夜同时审批/过期；若决定发生时已到 expires_at，必须过期而不是拒绝收费或批准执行。 | **PARTIAL** | 决定入口到期校验代码/核心测试存在；完整午夜并发与真实入口尚未验收。 |
| Q355 · [L837](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:837) | 已批准/生成跨日完成；扣原提交日；新日额度不被错误减少。 | **PARTIAL** | 状态固定原 quota_date，核心路径正确；跨日实际流式完成未端到端验证（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q356 · [L838](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:838) | 修改学生浏览器/资料时区；不影响额度日期。 | **PASS** | 核心日期来自教师时区，不读取学生浏览器/资料时区。 |
| Q357 · [L839](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:839) | 教师时区变化、DST、时钟回退；自然日正确、旧桶不可重复发放、历史不重写；异常有维护提示。 | **PARTIAL** | 有自然日和变更逻辑；无异常回退防护，真实 DST/Windows 环境矩阵未完成（[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q358 · [L840](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:840) | +1、-1、重传；adjustment 正确，used 不被改，重复操作不再调整。 | **FAIL** | 核心调整幂等通过，但实际 HTTP 相同头重放重复加次（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q359 · [L841](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:841) | 批量调整一人冲突或不足；整批不应用，明确显示冲突，无部分静默修改。 | **PARTIAL** | 核心不足/冲突事务回滚已测；真实接口版本缺省使旧预览可生效（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q360 · [L842](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:842) | 服务强杀后恢复；ledger 与日桶一致；active 唯一约束仍成立。 | **FAIL** | 没有自动恢复或启动对账，缺 active 唯一索引；重建实例复现遗留预留（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)）。 |

## K2. 审批、身份与绕过

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q361 · [L848](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:848) | 同一 request_id/operation_id 并发重复提交，相同内容只产生一份预留和一个请求。 | **PASS** | 核心相同操作并发只建一份，现有并发测试及审计模拟验证。 |
| Q362 · [L849](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:849) | 复用已批准 key 修改文字、模型、历史、图片或文件：409/重新审核，上游未发送替换内容。 | **PARTIAL** | 核心 payload/hash 变化冲突；chat/parent 等关联不绑定（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q363 · [L850](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:850) | 一个批准同时两个消费者：一次派发；重复事件、重复完成、重复 stop：一次结算。 | **PARTIAL** | 正常 claim/最终结算唯一通过；真实 stop/消费恢复缺陷未解决（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q364 · [L851](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:851) | 30 个学生各提交一问：30 个独立归属，最多 30 个活动请求，上游同时执行不超过配置。 | **PARTIAL** | 独立文件库 30 人模拟通过：30 调用、30 唯一请求、峰值 4；不是 30 浏览器实网且停止场景超限（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q365 · [L852](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:852) | 同学生跨设备/多标签 10 次并发：最多一个活动请求。 | **PARTIAL** | 核心单学生并发有效；真正跨设备/原生多标签还未运行。 |
| Q366 · [L853](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:853) | 教师双标签同时批准/拒绝，先提交者成功，另一端收到当前状态冲突。 | **PARTIAL** | 核心版本竞争正确；教师双标签浏览器与事件呈现未端到端运行。 |
| Q367 · [L854](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:854) | 匿名/学生访问教师决策、调额、导入、导出、8790 接口：拒绝。 | **PARTIAL** | 已测部分 standalone 教师权限拒绝；原生所有写接口/真实 8790 保护矩阵未全测（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q368 · [L855](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:855) | 伪造 body.user_id/name/role、X-Review-Token、内部签名头、旧签名重放：拒绝。 | **PARTIAL** | 直接用户控制字段和 HMAC 工具重放已有测试；运行中内部协议缺失、引导豁免仍在（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q369 · [L856](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:856) | 学生修改显示昵称，不改变名册名、user_id 和额度归属。 | **PASS** | 名册和额度存储采用稳定 user_id，学生昵称不作为核心归属。 |
| Q370 · [L857](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:857) | 旧 JWT 在首次改密/教师重置/退出后不能访问受保护 REST 和 WebSocket；无 Redis 环境也成立。 | **FAIL** | 未登记旧 JWT 重置后可懒登记，WS 无保护，原生到期不检查（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q371 · [L858](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:858) | 直接原生登录、原生改密、原生管理员重置与课堂界面具有一致效果。 | **FAIL** | 原生端点没有会话生命周期 hook（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q372 · [L859](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:859) | 未改初始密码、未 enrollment、pending/disabled 账号不能生成/上传/调用副接口。 | **FAIL** | 必改状态上传返回 200；原生副入口也未统一限制（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q373 · [L860](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:860) | /openai/chat/completions、/ollama、/api/v1/messages、embeddings、tasks/title、tasks/queries、自动摘要、audio/images、工具和直接提供商路径均验证零非授权上游调用。 | **FAIL** | 实际 middleware + 原始 handler 的 messages/embeddings 测试录到非授权出口调用（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q374 · [L861](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:861) | 学生在 /api/chat/completions 中伪造多模型、metadata.task、direct、工具参数、filter_ids 不能取消保护。 | **PARTIAL** | 核心拒绝部分危险字段；正常 chat 被一概拒绝不能证明受管聊天安全可用（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q375 · [L862](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:862) | 教师关闭 Filter/删除 Pipe/重新加入直接提供商、或升级路由清单变化时，readiness 变为失败并暂停学生模型访问。 | **FAIL** | readiness 不读取真实保护/installed 内容状态，缺适配生命周期（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q376 · [L863](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:863) | 本机匿名审批、跨源请求、恶意 Origin、错误 HMAC、过期 nonce 都不能成功决策。 | **PARTIAL** | HMAC 错签/过期/重放单元验证存在；Origin/CSRF 未实现，原生场景未全测（[M02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M02)）。 |

## K3. 附件与上下文

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q377 · [L867](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:867) | 纯文字、纯图片、文字+图片、纯 .py、文字+.py、混合多个文件均进同一审批队列。 | **FAIL** | 学生纯图/纯文件无法提交，原生混合附件没有接管（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q378 · [L868](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:868) | 教师预览和上游实际 payload 的文字、图片和哈希一致。 | **FAIL** | 教师无法看实际文件内容；有效历史未重建（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q379 · [L869](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:869) | 上传时未调用模型/嵌入/OCR/外部解析服务；更改 process=true 仍不能绕过。 | **FAIL** | 原生 process=true 仍可走处理分支，未强制零模型副调用（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q380 · [L870](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:870) | 批准后修改/删除原生附件、同名替换文件、伪造 file_hash：不能更改已批准输入。 | **PARTIAL** | 本地 blob/hash 绑定测试通过；原生附件变更/删除适配尚缺（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q381 · [L871](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:871) | 学生引用其他学生 file_id、路径穿越、file URL、内网 URL、巨大 data URI：拒绝。 | **PARTIAL** | 核心拒绝越权/file/网络 URL；原生 file_id 和大请求边界仍不完整（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q382 · [L872](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:872) | 超尺寸、伪装扩展名、解压炸弹型图片、SVG/HTML 主动内容、不支持编码：安全错误，不放行。 | **FAIL** | 伪 PNG 被接收，有效 WebP 被拒；完整安全解码未实现（[M01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M01)）。 |
| Q383 · [L873](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:873) | .py 只读为文本，不创建子进程执行文件；Python 教学不默认为服务器代码执行授权。 | **PASS** | .py 只读并注入为文本；代码路径及现有附件测试证实无执行。 |
| Q384 · [L874](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:874) | 修改后批准保留应有的图片和文本附件；后续追问不恢复旧原文。 | **PARTIAL** | 核心改写保留附件已测；后续追问会采用浏览器旧历史（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q385 · [L875](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:875) | 超上下文/不支持图像模型：本地说明，不静默丢附件、不擅自换模型。 | **FAIL** | 缺上下文预算和模型图像能力检查（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q386 · [L876](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:876) | 老聊天、分支、重新生成和被改写问题的上下文指纹稳定，学生不能注入未展示的历史。 | **FAIL** | chat/parent 不进 digest、无有效历史/分支重建（[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q387 · [L877](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:877) | 图片永久归档、教师导出后可离线查看，不仅有过期 URL。 | **PARTIAL** | 新课堂 blob 随 ZIP 导出可保留；完整旧图片与教师原生流程未接（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |

## K4. 账号、界面与导出

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q388 · [L881](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:881) | UTF-8 BOM、引号/逗号、空行、重复登录标识、大小写冲突、无表头/缺列、空密码、admin 角色注入、非法文件均有逐行结果。 | **PARTIAL** | 标准 CSV 的部分有效/无效场景通过；全无效提交结果丢失，原生冲突矩阵不足（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q389 · [L882](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:882) | 中途断网/服务崩溃后部分导入可恢复，不重复创建、不修改已有账号密码。 | **FAIL** | 没有跨重启恢复源文件/旧批次及完成重放（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q390 · [L883](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:883) | 导入尚未完成安全状态时账号仍受限；必须改密不可被直调 API 绕过。 | **FAIL** | 直接创建 user，实际首次改密/上传限制失败（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q391 · [L884](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:884) | 忘记密码教师重置后旧会话立即失效，下一次必须改密。 | **FAIL** | 原生先重置后撤销，未登记旧 JWT 仍可接受（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)）。 |
| Q392 · [L885](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:885) | 学生看到实时可用/预留状态；拒绝明确扣次；取消对话框不会提交拒绝或调额。 | **PARTIAL** | 有可用/预留和拒绝提示、prompt 取消；真实 LAN/UI 未通（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q393 · [L886](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:886) | 刷新/关闭后恢复不重发模型，状态与服务器一致；异常不会无限转圈。 | **FAIL** | 批准/生成刷新不恢复，Pipe 同步阻塞，事件消费链缺失（[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q394 · [L887](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:887) | 单人/全班对话导出包含原文、有效问题、回答、图片/代码、时间、状态和扣次依据；拒绝/过期/故障同样保留。 | **PARTIAL** | 新请求 ZIP 有文本/附件/账目；原生对话、完整过滤和哈希清单不全（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q395 · [L888](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:888) | 旧原生聊天通过原生管理员 API 导出，不因缺课堂 request_id 而漏掉；重复归档有 provenance，不冒充不同问答。 | **FAIL** | 无原生管理员聊天读取路径（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q396 · [L889](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:889) | 学生隐藏/删除原生聊天不影响教师永久归档；导出不能越过教师授权范围或包含任何密码/Key。 | **PARTIAL** | 新课堂独立数据不随原生删除；旧对话长期留存/全数据保密尚未整体验证（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q397 · [L890](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:890) | 同名学生导出不覆盖，CSV 不执行公式，Markdown/HTML 预览无脚本注入。 | **PARTIAL** | ID 文件名/CSV 防公式实现可核对；Markdown/HTML 浏览器主动内容未做实测，不宣称通过。 |
| Q398 · [L891](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:891) | 无敏感真实数据的示例名册、示例对话和教程截图可正常使用。 | **PARTIAL** | 有无真实密码的名册模板/简化导出样例；缺完整真实结构样例和可用教程截图（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |

## K5. 部署、故障与升级

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q399 · [L895](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:895) | 干净 Windows x64，没有系统 Python/Node/Docker；中文空格路径、换盘解压均能启动。 | **FAIL** | 隔离 Python 导入和空格参数已失败；干净 Windows/换盘整包未测（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)、[H19](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H19)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q400 · [L896](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:896) | 无依赖下载的启动成功；教师机能联网访问上游。完全断网时显示上游不可用并零扣，不宣称仍能回答。 | **NOT VERIFIED** | 没有完整最终包的无下载启动/真实提供商断网联合验收；本轮只使用模拟上游。 |
| Q401 · [L897](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:897) | 单服务失败、端口被其他程序占用、双击重复启动、旧 PID 被复用、自定义 DataRoot、强杀恢复均可预测。 | **FAIL** | 半启动、端口身份、DataRoot 与停止记录存在代码缺陷（[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)）。 |
| Q402 · [L898](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:898) | bootstrap/迁移/Pipe 安装失败时学生模型出口关闭，不能只因为 /health=200 开放。 | **FAIL** | 维护 marker 有局部拒启，但实际 readiness/旁路保护未完成（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q403 · [L899](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:899) | 备份在副本恢复后能登录、查看聊天、恢复附件和额度，两个库及 blob 引用一致。 | **FAIL** | 备份缺原生库且恢复先覆盖后校验，无法通过（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)、[H18](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H18)）。 |
| Q404 · [L900](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:900) | 低磁盘、归档写失败、SQLite busy/locked、服务间请求超时都不丢已收费回答或重复扣次。 | **PARTIAL** | 正常文件 SQLite 并发已测；低磁盘/IO 失败/跨服务超时矩阵缺失，缺资源保护（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q405 · [L901](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:901) | 停服务/升级没有长时间持有 SQLite 写锁；无无限内存队列或线程增长。 | **PARTIAL** | 正常事务不等待上游；Pipe 阻塞、全部导出入内存、真实停止与持续资源限制不足（[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q406 · [L902](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:902) | 当前精确版本回归通过；升级到其他版本要重新生成路由清单、校验 extension/API 契约并跑关键用例，不自动接受未知版本。 | **FAIL** | 准确版本实际调用契约已发现失败；静态 compatibility 不能防未知版本（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)—[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)）。 |
| Q407 · [L903](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:903) | 发行 ZIP 不含真实 data/logs/凭据/初始密码，校验文件匹配，源码构建可重现组件版本。 | **FAIL** | 没有新发行 ZIP/完整锁和可复现组件清单，打包筛选不安全（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q408 · [L904](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:904) | 正常课堂 UI 的提交/状态接口，在 30 人并发和本地模拟快速依赖下，目标 p95 < 2 秒；教师决定到事件可见目标 < 2 秒。模型生成耗时单独统计，不用上游速度掩盖本地阻塞。 | **NOT VERIFIED** | 未跑 30 浏览器/完整同源 API p95 与决定可见延迟测试；核心 30 人测试不替代此项。 |

## L. 分阶段实施顺序

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q409 · [L912](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:912) | 0 基线与隔离；classroom 源码归档、版本清单、模拟上游、数据副本、备份恢复；可重现现状并安全开发；dist 被忽略、误操作现有数据；确认副本隔离；旧数据数量和哈希记录；模拟复现 C01/C03/H01 | **PARTIAL** | 部分源码目录/哈希/模拟测试已建立；原始源码快照、完整可恢复基线不全（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q410 · [L913](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:913) | 1 集成可行性与出口封闭；Pipe 原型、bridge/route_guard、run_openwebui、准确版本兼容清单；普通聊天/图片/文本能进入唯一模拟出口，旁路零调用；Pipe 前隐含 AI 调用；前端扩展不支持；实测 file_handler、process=false、身份与首次改密挂接位置；确定最小补丁清单；全旁路断言通过 | **FAIL** | 真实 Pipe/模型/文件/路由/身份契约失败，旁路已复现（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)—[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q411 · [L914](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:914) | 2 数据与额度核心；migrations、database、quota、requests、ledger；R02—R08 的预留/扣次/调整/跨日正确；重复结算、锁竞争、日界错误；K1 和并发幂等测试全通过；崩溃恢复账目一致 | **PARTIAL** | 额度核心有可复用成果；HTTP 幂等、自动过期/恢复和 DB 对账未完成（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)、[M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)）。 |
| Q412 · [L915](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:915) | 3 安全账号生命周期；authentication、security_states、原生登录/重置 hook、accounts；批量导入后必改密，重置撤销旧会话；双库半成功、保留原生绕过入口；K2 认证及 K4 导入测试通过；无 Redis 场景覆盖 | **FAIL** | 原生认证与账号安全顺序失败（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)—[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q413 · [L916](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:916) | 4 执行与恢复；worker、Pipe 流、response_events、cancel、consumer lease；批准才发送；成功/拒绝/主动停/故障准确结算，可重放；POST 结果未知被自动重试、截断流假成功；模拟上游强杀/断网/午夜竞争通过；一个授权一次派发 | **PARTIAL** | 有 worker/attempt/events；实际派发、流完成、停止、重启恢复失败（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)—[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)）。 |
| Q414 · [L917](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:917) | 5 附件与历史；attachments、Filter、文件 adapter、archive、上下文重建；教师审核内容等于实际送模内容，留存原文和有效版本；附件可变、RAG 副调用、原文回退；K3 全通过，确认不执行 Python 文件、不隐式外发 | **PARTIAL** | 本地 blob/快照有效；教师实际审阅、文件接管、有效上下文与旧历史未完成（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)—[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q415 · [L918](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:918) | 6 教师和学生 UI；classroom web、必要原生前端小补丁、同源 APIs；额度、审核、单人/批量调整、首次改密、停止和恢复可用；界面成功但后端未约束、弱网重复操作；K4 UI 测试；教师使用流程实测；后端对直调 API 同样强制 | **PARTIAL** | 两张页面原型存在；挂载不可达、重要操作缺失、LAN HTTP 不兼容（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H21](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H21)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q416 · [L919](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:919) | 7 导出与日常运维；exports、Backup/Restore/Start/Stop/Status/Firewall、说明书；永久记录可导出，备份可恢复，单服务故障可修复；ZIP 漏数据/漏附件/带密钥，备份不一致；导出清单与归档对账；全备恢复测试；K5 基础部署通过 | **PARTIAL** | 有导出/脚本骨架；全备、非破坏恢复、运维与指南不合格（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)—[H19](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H19)、[M07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M07)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q417 · [L920](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:920) | 8 迁移演练与正式包；migration baseline、legacy adapter、Build-Package、release manifest；旧用户/聊天/附件保留，新额度从切换日生效；错误 Alembic 基线、覆写旧数据、回滚丢增量；J 节完整演练；30 人并发及关键矩阵全过；干净 Windows 解压验证 | **FAIL** | 没有旧数据迁移/回滚演练和新完整发行 ZIP（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q418 · [L921](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:921) | 9 交付与运行验收；最终包、校验、源码说明、测试报告、教师指南；教师能独立启动、导入、审核、调额、重置、导出和恢复；未测项被宣称完成；明确列出已测/未测；提供可执行命令和证据；通过下面总验收 | **FAIL** | 缺教师独立使用验收，已知阻断仍在；不能以未测真实模型概括（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |

## 总验收清单

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q419 · [L925](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:925) | 所有学生可用模型能力均不能跳过审批与额度。 | **FAIL** | 存在实际非授权出口调用（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)）。 |
| Q420 · [L926](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:926) | 教师拒绝扣 1 次；正常成功扣 1 次；意外中断零次；有回答后学生主动停止扣 1 次。 | **PARTIAL** | 拒绝/正常成功核心正确；截断和主动停止分类错误（[H09](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H09)、[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q421 · [L927](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:927) | 同一操作最多一个预留、一个最终结算、一个对外派发。 | **PARTIAL** | 正常核心 reserve/attempt/settle 唯一；原生操作恢复与真实执行链未完（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)—[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q422 · [L928](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:928) | 教师机时区的日界正确，跨日待审移出队列但保留全部历史。 | **PARTIAL** | 日桶算法存在；自动过期、时区异常保护失败（[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)、[M06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M06)）。 |
| Q423 · [L929](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:929) | 单人和全班批量调整可用，历史不可被清零。 | **PARTIAL** | 核心批量正确；UI/API 幂等/全选/自定义不全（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q424 · [L930](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:930) | 批量账号强制首次改密、教师重置可用，旧令牌确实失效。 | **FAIL** | 首次改密/重置和旧 JWT 撤销失败（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)—[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q425 · [L931](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:931) | 图片与 .py 等文本文件真实可审、实际送模内容一致。 | **PARTIAL** | 有不可变文件核心；教师不能审实际附件、原生文件未接（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)）。 |
| Q426 · [L932](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:932) | 永久对话/附件归档及教师导出可用，学生删改不破坏留存。 | **PARTIAL** | 新课堂归档存在；旧对话/完整会话和导出缺失（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q427 · [L933](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:933) | 30 人并发、服务重启、网络中断、双决策和幂等重试测试通过。 | **PARTIAL** | 30 个核心测试及独立 30 人模拟通过；完整恢复/网络/原生 UI 关键矩阵失败或未测。 |
| Q428 · [L934](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:934) | 现有用户 ID、旧聊天、附件、审批完整迁移；没有追扣旧记录。 | **FAIL** | 没有用户/旧聊天/附件/审批的完整迁移（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q429 · [L935](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:935) | 便携包可换盘、中文路径运行，干净机器无额外依赖下载。 | **FAIL** | 完整启动、空格路径失败且没有最终发行包（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)、[H19](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H19)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q430 · [L936](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:936) | 备份恢复和受保护回滚已演练，发行包不带真实数据或秘密。 | **PARTIAL** | 局部备份/导出存在；全备恢复、回滚和安全新包验收未通过（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)、[H18](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H18)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |

## 交付物要求

| 编号 / 原计划定位 | 原计划要求 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q431 · [L940](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:940) | 受版本控制的课堂源码、明确依赖锁、准确版本兼容适配和必要的最小补丁。 | **PARTIAL** | 新 classroom 目录存在但当前未纳入提交；锁无完整哈希、准确版本集成失败（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)—[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q432 · [L941](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:941) | Windows x64 全新发行 ZIP、SHA256、组件清单；另提供原安装升级方式，不能用新包 data 覆盖旧数据。 | **FAIL** | 没有新 Windows 完整 ZIP、SHA256 和可执行升级交付（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q433 · [L942](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:942) | 迁移脚本、迁移审计报告、备份恢复和回滚说明。 | **PARTIAL** | 有 schema 清单和局部 Backup/Restore；缺完整迁移/报告/受保护回滚（[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)、[H18](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H18)、[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q434 · [L943](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:943) | 有实际执行证据的测试报告；注明纯模拟与真实模型验证的区别。 | **PARTIAL** | 有测试及结果记录，本轮重跑 30 通过；原报告对真实集成完成度夸大（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q435 · [L944](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:944) | 中文教师使用说明：启动/关闭、导入与初始密码、学生改密、拒绝扣次、单人/批量调额、暂停、历史导出和密码重置。 | **PARTIAL** | 有新中文指南；与 UI/API 命令行为及发行包不一致（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q436 · [L945](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:945) | 示例账号模板、无敏感数据的导出样例；不得夹带本班真实密码。 | **PARTIAL** | 有模板和简化无敏感数据样例；缺完整可用对话 ZIP 样例及全字段校验（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q437 · [L946](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:946) | 已知限制：单班单教师、单实例、受管模型、首版附件范围、没有本机执行学生 Python、永久留存的容量管理边界。 | **PARTIAL** | 说明列出部分范围边界；未充分披露执行、安全、恢复和容量缺口（[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |

## 正文中的补充要求与执行约束

| 编号 / 原计划定位 | 原计划段落 | 状态 | 核验结论 / 证据 |
|---|---|---|---|
| Q438 · [执行约束 · L10](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:10) | 请先完整阅读本文，再检查实际文件是否仍与基线一致。按 L 节逐阶段实施，完成阶段测试后再进入下一阶段。不得把“界面出现了审核按钮”或“普通聊天能暂停”等同于审批已经不可绕过。 | **FAIL** | 阶段 1 的真实集成与出口契约未完成，却把后续核心测试写成阶段完成（[H01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H01)—[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q439 · [执行约束 · L12](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:12) | 只修改课堂系统相关组件，不改造主仓库 Sub2API 的 Go/Vue 网关、计费和业务代码。保留已有用户 ID、账号、聊天、附件及审批历史。开发、迁移演练和故障测试使用隔离的数据副本与模拟模型；最终交付可解压使用的 Windows 包及迁移、回滚、备份说明。不要主动使用生产上游做压力测试。 | **PARTIAL** | Go/Vue 业务未见相关改动，范围控制正确；旧数据迁移、可用新包和恢复交付仍缺（[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)—[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q440 · [执行约束 · L14](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:14) | 本文的用户决策优先于旧说明书和旧 Filter 行为。实现细节可以根据证据调整，但不得弱化审批、身份、计数、数据保留和首次改密要求。遇到本版本不支持的扩展接口，先验证可行替代，不得假设最新版文档中的接口已经存在。 | **FAIL** | 异常中断、主动停止、必改密和永久旧历史要求被弱化；准确版本扩展行为未验证（[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)—[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q441 · [A1 源码与范围 · L89](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:89) | 没有发现适用于课堂组件的 AGENTS.md。课堂自有文件目前位于被 Git 忽略的 dist 中，未发现完整受版本控制的课堂源码和可重复打包流程。实施前应建立独立源码目录，而不是长期直接修改发行产物。 | **PARTIAL** | 新增 classroom 独立源码目录；当前 Git 仍是 untracked，发行包不是可重复构建的新完整包（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q442 · [A2 关联约束 · L102](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:102) | Open WebUI 的“message_id”在普通界面生成路径中通常是回答消息 ID；另有“user_message_id”。实施者不得混用二者，否则重生成、重复点击和分支聊天的幂等关系会错误。 | **FAIL** | 原生 user/assistant message_id 与操作恢复未接，关联也不进 digest（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q443 · [A4 复用约束 · L133](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:133) | 当前 CSV 导入器按换行和逗号拆分，无法完整解析引号内逗号/换行，并可能部分成功。可以继续复用建号 API，但本次名册导入必须增加可靠解析、校验、强制改密标记和恢复能力。 | **PARTIAL** | 已换标准 CSV 解析器并复用建号 API；必改安全顺序、冲突预览和批次恢复缺失（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q444 · [C1 选定范围 · L192](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:192) | 本期采用第三种。它不是深度分叉 Open WebUI：优先使用原生 Functions、文件和用户 API；课堂登录约束、API 防护和状态页面通过独立适配模块接入当前启动器。若原生前端没有可用扩展位置，允许一份针对准确版本的最小源码补丁，范围仅为首次改密跳转、课堂状态/操作标识、附件上传及停止事件。禁止修改压缩后的 JS 字符串、维护无边界 monkey patch 或顺带重写 Open WebUI。 | **PARTIAL** | 组件命名遵循 Pipe+服务；实际多个 Service/直接出网，最小前端适配未完成（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)—[H05](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H05)）。 |
| Q445 · [C2 教师权限 · L220](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:220) | 教师仍具完整管理员权限，可以改模型、导入学生、调整次数和导出数据。若教师人为修改安全配置，课堂自检应报告不满足保护条件并暂停学生调用；这不是限制教师管理权限。 | **FAIL** | middleware 未区分教师，封锁模型/配置/函数管理；配置破坏未引发真实自检失败（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q446 · [C3 上下文隔离 · L239](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:239) | 可信请求上下文必须隔离到具体操作，不能放进共享 Filter/Pipe 实例的可变属性。当前 Open WebUI 某些路径会复用 request/state 和插件实例；使用明确的不可变操作上下文、服务端覆盖的关联值或任务隔离机制，避免并发学生串号。来自 metadata 的 task、user_id、request_id 不因参数名看起来“内部”就自动可信。 | **PARTIAL** | service 方法以明确 ID 传参、未见保存单个学生到共享属性；metadata 的可信注入/原生并发契约未接（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q447 · [C4 预留语义 · L243](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:243) | 使用“预留”和“正式使用”分开记录。提交会降低界面可用次数，但只有最终收费状态才增加 used。 | **PASS** | 核心 reserved/used 分离，提交与结算分别写 ledger，现有测试与独立并发验证。 |
| Q448 · [C4 可展示回答 · L259](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:259) | “已有回答”依据服务端已经持久化并交付到有效聊天订阅的可展示正文事件，不能把 HTTP 200、心跳、provider usage 或隐藏思考字段当作回答。停止请求记录学生主动动作及最后接收序号；这类接收声明只能影响计数分类，不能给予新调用权。不能只信任客户端声明“网络错误”而退款。 | **FAIL** | 没有有效订阅 delivered_seq，以写入字节代替收到正文（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q449 · [C4 终态竞争 · L261](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:261) | 同一终态只能结算一次。完成、主动停止、故障、午夜过期同时到达时，通过状态版本和事务产生唯一结果。任何重复事件都返回已确定状态，不新增 ledger。 | **PARTIAL** | 终态 ledger 唯一及事务保护已测；stop 与 claim 的实际竞争未正确完成停止（[H10](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H10)）。 |
| Q450 · [C4 午夜决定 · L263](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:263) | 待审在当日最后一个瞬间之后不再能被批准或拒绝收费：教师点击时必须先执行到期检查。后台清理定时器只是辅助，不能是唯一保证。 | **PASS** | 核心 decide 在收费/批准前检查 expires_at，不依赖后台定时器作唯一保证。自动移出见 [H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)。 |
| Q451 · [C4 跨日归属 · L265](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:265) | 已批准排队或生成中的请求跨日继续归属于提交时的日额度；用户要求清理的是“仍待审”请求。第二天新额度按新日桶产生，但“每人一个活动请求”仍跨日生效。不要把跨日完成扣到第二天。 | **PARTIAL** | 请求固定原日桶；实际生成/重启恢复未接，跨日正常运行仍需契约验收（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H11](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H11)）。 |
| Q452 · [D 数据职责 · L295](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:295) | 原则：Open WebUI 继续拥有原生 auth/user/chat 表；课堂服务使用自身数据库及迁移。不要往第三方 user 表随意加 quota 字段，不直接写原生密码哈希。下面是逻辑模型，可合并物理表，但字段语义、约束和事务边界不能丢失。 | **PARTIAL** | 未手写第三方密码哈希；独立 DB 合理，实际账号安全联动和原生历史读取未完成（[H07](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H07)、[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)、[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q453 · [D1 秘密隔离 · L305](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:305) | 提供商 API Key 等秘密不放入可导出的 settings 表；另用本机受限凭据文件/Windows DPAPI 保存。迁移到新电脑必须有明确重新输入密钥的流程，不能只复制 DPAPI 密文宣称可用。 | **PARTIAL** | 快照/导出不主动含 Key；唯一服务受管密钥存储和跨机重配尚未实现（[C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H17](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H17)）。 |
| Q454 · [D2 删除后归档 · L318](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:318) | 原生账号删除后保留此记录为归档身份，不级联删除历史。新账号即使邮箱相同也不能自动继承旧用户 ID。 | **PARTIAL** | 独立 students/request 外键不指向第三方库，不自动级联删；deleted_origin/原生事件适配尚缺（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)、[H16](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H16)）。 |
| Q455 · [D3 登记与时限 · L332](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:332) | 只在服务端确认原生密码登录成功之后登记会话；不能在第一次见到任意有效旧 JWT 时自动登记。默认课堂学生会话最长 12 小时且不超过原生 JWT 过期时间；教师可调。临时初始会话只有改密能力。详细安全顺序见 H3。 | **FAIL** | register_native_token 懒登记且不检查原生课堂会话 expires_at（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q456 · [D4 约束与对账 · L344](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:344) | 非负校验：used >= 0、reserved >= 0、base_limit + adjustment >= used + reserved。本期单活动请求下每人的 reserved 最大为 1。日桶可由 ledger 重算核对，数据库事务不能只更新其中一边。 | **PARTIAL** | used/reserved 各自非负存在；总额关系/reserved<=1 约束和 ledger 对账缺失（[M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)）。 |
| Q457 · [D5 索引 · L363](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:363) | 为 user_id + 活动状态建立部分唯一索引。为 status/submitted_at/id、user_id/submitted_at/id、pending/expires_at 建索引。按稳定游标分页，不能只使用时间戳导致同秒问题丢失。 | **PARTIAL** | 列表/过期普通索引和核心复合游标存在；无活动部分唯一索引，原生 API 不透传 cursor（[M04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M04)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q458 · [D6 持久化成本 · L377](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:377) | 避免一个 token 一次 SQLite fsync：有界合并流片段，例如 200 ms/4 KiB 批量持久化，先持久化再对外发出。终态前刷盘并原子结算。归档对象通过临时写入、校验和原子改名发布；磁盘写入失败属于意外中断，不能成功计数但丢回答。 | **FAIL** | 每 delta 开事务并重写整段正文；缺批量合并/总量边界及归档失败完整场景（[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q459 · [D7 唯一结算 · L390](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:390) | 每个 request_id 只能有一个最终结算 ledger，使用唯一约束而不是仅靠 Python if。教师调整幂等键按教师 + 操作类型绑定规范化请求体；同键异体返回冲突。 | **PARTIAL** | 有最终 settlement 唯一索引；调整核心 key+body 绑定可用，但实际 header 未接（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q460 · [D8 文件边界 · L403](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:403) | 实际文件在 data/classroom/blobs 下按随机 ID 或内容哈希组织，不接受客户端绝对路径；所有下载经过身份/所有权校验。正文与附件永久保留，不能仅保存会失效的 URL。未提交临时上传可在 7 天后清理，但不能清理任何已引用对象。 | **PARTIAL** | 本地 hash 存储与归属检查有效；无内容下载路由、未提交附件永不清理（[H14](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H14)、[M03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M03)）。 |
| Q461 · [D9 密码短期保存 · L413](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:413) | 导入预览中的初始密码只短暂存在于受限内存；教师确认后执行，完成/超时销毁。需要重试时重新提供源文件或让教师重置，不能为方便恢复而存长期明文。导出的初始密码清单是用户明确请求的敏感一次性交付，和普通历史导出严格分开。 | **PARTIAL** | 密码在内存预览、未入持久表；过期清理/崩溃恢复与一次性交付链不完整（[H08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H08)）。 |
| Q462 · [E 外部身份协议 · L427](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:427) | 所有外部课堂 API 位于 Open WebUI 同源 `/api/classroom/v1`，由适配层验证原生用户和课堂会话，再对内部服务签名调用。不要让学生浏览器直接持有服务令牌访问 8790。 | **FAIL** | 3000 追加路由被 SPA 遮挡；没有签名调用内部业务 API，而是多个 Service 直接访问 DB（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q463 · [E2 正式聊天路径 · L474](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:474) | 正式问题通过原生聊天 API → 适配层 → Pipe → 内部 requests 提交。不要再造一个允许浏览器自填可信身份、批准状态或提供商密钥的直接生成接口。 | **FAIL** | 实际自建浏览器请求代替原生聊天；原生 Pipe 所需可信操作关联未实现（[H03](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H03)、[H15](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H15)）。 |
| Q464 · [E3 调额响应 · L511](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:511) | 响应包含 batch_id、applied、所有学生 before/after 和审计 ID。同一 Idempotency-Key 再次提交相同内容返回原结果；不同内容 409；跨日提交旧预览不静默操作新日桶。 | **FAIL** | 核心返回结果/事务可用，实际重复 Idempotency-Key 会二次应用、跨日旧预览未拒绝（[H13](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H13)）。 |
| Q465 · [E4 HMAC 范围 · L527](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:527) | 服务认证采用安装实例独有密钥生成 HMAC：覆盖方法、路径、正文哈希、时间戳、nonce 和经过验证的 principal；短时间窗并防重放。学生提供的同名 HTTP 头必须删除并由服务端重新构造。密钥不能出现在浏览器、Filter UserValves、日志或导出中；不能接受“签名有效但主体随学生 body 任意填写”。 | **PARTIAL** | 签名类覆盖方法/路径/body/time/nonce/principal 且有单测；只用于 readiness，实际业务未接（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)）。 |
| Q466 · [E4 执行权边界 · L529](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:529) | worker 领取和完成属于同一服务内部函数，不开放给学生或教师直接 POST /complete 扣费。若实现为内部 API，也必须绑定 attempt claim_token 与唯一快照，不接受客户端自报成功。 | **PARTIAL** | 没有开放客户端 /complete；claim 唯一可用，但生产所有者/实际派发验证不完整（[H04](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H04)、[H12](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H12)）。 |
| Q467 · [F 教师界面入口 · L543](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:543) | 教师通过 Open WebUI 管理员身份访问同源课堂管理页。首页显示三个主要区域：待审核、学生额度、历史/导出。 | **PARTIAL** | native teacher 依赖存在；页面不可达且缺历史区域（[H02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H02)、[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q468 · [F2 名册列 · L558](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:558) | 每行：姓名、登录标识、默认 3、今日增减、已使用、预留、可用、暂停状态。 | **PARTIAL** | 有姓名/login/可用/used/reserved；默认值、今日增减、暂停状态不完整（[M08](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#M08)）。 |
| Q469 · [G2 附件范围 · L600](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:600) | “文本类文件”在首版指能可靠按文本读取的教学材料。不要因此自动增加 OCR、RAG、Office 转换、任意文件执行等大范围能力。 | **PASS** | 新 AttachmentStore 限定可读教学文本，没有新增 Office/OCR/Notebook 执行处理；原生旁路另见 [C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)。 |
| Q470 · [H1 源码结构 · L620](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:620) | 建立项目根目录下受版本控制的 `classroom/`，不把生成物、数据和便携运行时提交入库： | **PARTIAL** | classroom 已建立、运行数据有 ignore；源码尚 untracked，Build-Package 不遵守安全数据清单（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q471 · [H1 物理文件可合并 · L668](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:668) | 这是职责分界，不要求机械生成每个文件。不要再建立另一套与服务相互竞争的 quota/checker。 | **PARTIAL** | 把请求/设置方法合并进 service.py 可接受；多份外部 API 和不同安全验证造成实际漂移（[L02](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L02)）。 |
| Q472 · [H1 基线与中文入口 · L670](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:670) | 先原样保存当前自有源码基线，之后再分模块演进。生成的发行包仍可保持教师熟悉的中文 CMD 入口。 | **PARTIAL** | 只有 manifest 未见原样源码快照；旧中文 CMD 保留但新正式发行包未完成（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)、[L01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#L01)）。 |
| Q473 · [H3 适配范围 · L695](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:695) | 可通过当前启动器安装明确的 ASGI 适配或经过测试的原生路由 hook。不得用无限制通用响应改写来捕获任意正文，只处理已锁定的认证端点，并限制缓冲大小。原生登录 UI 也必须进入这条登记流程；另做一个安全登录页却保留不受保护的原生登录不算完成。 | **FAIL** | 没有当前原生成功登录 hook；没有新建安全页可替代原生边界的理由（[H06](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H06)）。 |
| Q474 · [I/J 不把原生表当迁移完成 · L789](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:789) | 当前库由 create_all 构建，不能仅因为表名存在就认定等于 Alembic head。 | **PARTIAL** | launcher 要求 verified marker，避免直接 stamp 是正确的；没有真实等价证明/基线修复（[H20](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#H20)）。 |
| Q475 · [K 出口断言 · L820](E:/codex-work/sub2api/CLASSROOM_AI_IMPLEMENTATION_PLAN.md:820) | 所有测试先用可观测模拟上游记录“实际 POST 次数、payload hash、调用时间、返回事件”。安全测试以模型出口零调用为断言，不能只检查 HTTP 错误或界面状态。 | **PARTIAL** | 有 RecordingUpstream/核心单测；原实施路由测试多数只看拒绝/纯 RouteGuard，未验证所有真实出口；本轮补出的反例见 [C01](E:/codex-work/sub2api/CLASSROOM_AI_POST_IMPLEMENTATION_AUDIT.md#C01)。 |

## 使用本表进行复验

整改时先处理完整报告中的 P0/P1 阻断，保留核心已通过的事务与不可变快照设计；然后逐行更新证据。实际教师/学生入口、原生会话、文件、提供商模拟出口、进程重启和最终发行目录必须参与复验。只重复直接调用 Service 的单元测试，不能把此表中的集成 FAIL 改为 PASS。

