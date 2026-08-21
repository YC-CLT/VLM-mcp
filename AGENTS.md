# AGENTS.md

## 环境

- Python 3.11，uv 管理依赖
- config.py 集中配置所有常量，pyproject.toml 管理依赖
- **命令**：用 `cmd-exec-mcp`

## 关键文件

## 关键常量

## 规则

- **monkeypatch 必须用 `import config` + `config.X`**：`from config import X` 创建本地副本，monkeypatch 无法穿透；executor 同理 patch `executors.模块名.X`
- **config 重命名全量 grep**：常量改名/移除后搜索所有引用
- **跨 Task 依赖等待**：并行派发时先检查上游产物是否存在

## 查文献指南

## 工具

- 部分工具有相应的skill
- MCP详见 `mcp_tools_summary.csv`
- `Read` 无法访问 `D:\Temp`，MCP 长输出需 `Copy-Item` 到项目根目录，正则替换 `\\n` 为 `\n`
- **Edit `replace_all` 错误**：`replace_all=True` 无法使用。优先用 PowerShell `Select-String` + 正则做精确替换，或手动逐处 Edit
- 浏览器操控用 `chrome-devtools-edge`（Edge CDP），**禁止用 `cua-driver` 操控浏览器**
- **WebFetch 无法使用**：用 `wet-mcp extract`

## 工作流

0. 读AGENTS.md
1. 构想：调用 brainstorming → 产出 `docs/superpowers/specs/<date>-design.md`
2. 计划：调用 writing-plans → 产出 `docs/superpowers/plans/<date>-plan.md`
3. 发派：调用 dispatching-parallel-agents 产出给n号机（目前只有1，2号机）的提示词 `docs/superpowers/subprompts/<date>-plan-subprompt-n.md` ，用于手动发派（当前环境是win且不支持子代理，无法自动 dispatch），创建`docs/superpowers/subprompts/<date>-plan-process.md` 用于记录进度，防止冲突
4. 实施：调用 executing-plans
   - 先隔离，使用git创建新的dev分支（1号机）或者进入已有分支（2号机）  
   - 遇到 bug 自动触发 systematic-debugging（先找根因再修）
   - 写代码自动触发 test-driven-development（先写测试再实现）
5. 验证：调用 verification-before-completion → 跑验证命令确认完成
6. 记录：调用 writing-agents → 写CHANGELOG.md + 经验教训到AGENTS.md
7. 提交：调用 finishing-a-development-branch → 分组提交

## 经验/坑点
