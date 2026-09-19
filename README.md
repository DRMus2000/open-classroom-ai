# 课堂 AI（open-classroom-ai）

Open WebUI 0.11.2 的课堂审批集成：独立审批/额度/执行服务、原生登录与文件桥接、教师管理页与学生提问页。当前测试候选版本 **2.1.8**。

源码仓库：https://github.com/DRMus2000/open-classroom-ai

2.1.8 审计修复补丁（`2.1.8-audit1`）修复审核解析、附件审核、调度、重试恢复、教师上传和访客分享地址。已有 2.1.8 安装参见 [补丁安装说明](PATCH_2.1.8_README.md)，通过 `scripts/Build-Patch.ps1` 构建程序补丁包。

完整便携 ZIP 由 `scripts/Build-Package.ps1` 构建（输出名含版本号，如 `openwebui-classroom-2.1.8-windows-x64.zip`），含 Python 3.11.9 与已有完整运行时，不含真实账号、聊天、上传文件或密钥。不要把工作区的 `rehearsal`、旧发行目录或实际 `data` 手动复制进发行包。

## 文档

| 文档 | 用途 |
|---|---|
| [TEACHER_GUIDE_CN.md](TEACHER_GUIDE_CN.md) | 教师安装、日常使用与运维 |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | 当前版本实现与验证边界 |
| [docs/CLASSROOM_AI_REQUIREMENTS.md](docs/CLASSROOM_AI_REQUIREMENTS.md) | 现行需求与验收标准 |
| [docs/README.md](docs/README.md) | 文档索引（含历史审计说明） |
| [NOTICE](NOTICE) / [LICENSE](LICENSE) | 许可与第三方声明 |

`docs/reference/` 与部分审计报告保留修复前证据，**不代表当前源码状态**；以实施状态与需求文档为准。

## 许可

- 本仓库中的课堂服务、桥接、Pipe/Filter、教师/学生页面、脚本与文档：见 [LICENSE](LICENSE)（MIT）。
- 便携发行包内嵌的 Open WebUI 仍受 Open WebUI 自身许可约束：见 [NOTICE](NOTICE) 与 [third_party/open-webui/](third_party/open-webui/)。再分发含 Open WebUI 的二进制包时，须保留其版权声明与许可文本，且不得擅自去除 Open WebUI 品牌标识（除非符合其许可中的例外条件）。
- 本项目不是 Open WebUI 官方产品，也不构成对 Open WebUI 的背书。
