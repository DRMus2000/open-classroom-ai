# 课堂 AI：整改候选版本

本目录是 Open WebUI 0.11.2 的课堂审批集成。提供单独的审批/额度/执行服务、原生登录和文件桥接、教师管理页与学生状态页。

完整便携 ZIP 由 `scripts/Build-Package.ps1` 构建，包含 Python 3.11.9 及已有完整运行时，不包含真实账号、聊天、上传文件或密钥。不要把工作区的 `rehearsal`、旧发行目录或实际 `data` 手动复制进发行包。

首次使用及迁移步骤见 [教师指南](TEACHER_GUIDE_CN.md)。验证范围和剩余验收项见 [实施状态](IMPLEMENTATION_STATUS.md)。原始审计报告保持不变，作为修复前证据。

## 许可

- 本仓库中的课堂服务、桥接、Pipe/Filter、教师/学生页面、脚本与文档：见 [LICENSE](LICENSE)（MIT）。
- 便携发行包内嵌的 Open WebUI 仍受 Open WebUI 自身许可约束：见 [NOTICE](NOTICE) 与 [third_party/open-webui/](third_party/open-webui/)。再分发含 Open WebUI 的二进制包时，须保留其版权声明与许可文本，且不得擅自去除 Open WebUI 品牌标识（除非符合其许可中的例外条件）。
- 本项目不是 Open WebUI 官方产品，也不构成对 Open WebUI 的背书。
