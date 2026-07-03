# 智能代码记忆与安全回退工具 (Conversation Memory)

本项目为 Google Antigravity 系统定制开发了一个智能记忆与代码精准回退的全局插件。它主要用于在 AI 进行多轮代码修改时，通过在物理上为当前修改做快照，从而在用户说“改得不对，退回到第二次修改”等恢复要求时，能通过历史快照列表**100%精准无损地**回滚代码，有效防止 AI 乱改乱恢复的问题。

本工具完美适配 **Google Antigravity (IDE / CLI / Agent)** 全系列官方套件、**Gemini CLI (agy)**，并同样完美兼容 **Cursor、Claude Code、Windsurf、Copilot** 等主流 AI Agent 平台，实现跨环境、零配置、开箱即用的备份与安全回退防护。

---

## 目录结构
```text
e:\GPT\conversationMemorySkill\
├── .cursorrules           # 主流 AI 编辑器本地规则
├── scripts/
│   └── checkpoint.py      # 本地版本管理核心 Python 脚本
└── README.md              # 本说明文档
```

---

## 核心机制：增量按需快照与双向事务还原
与普通的简单目录打包备份不同，本工具借鉴了 Git 底层数据库的设计精髓：
1. **去重存储**：备份文件以内容的 SHA256 哈希值作为文件名存储在 `.checkpoints/store/<sha256>` 下。相同内容的文件无论属于哪个版本，在磁盘上都只占用一份空间。
2. **增量按需备份 (On-Demand Backup)**：AI 助手在每次准备修改代码前，仅通过 `--files` 指明其本轮计划修改或新建的特定文件。脚本**只针对这些文件**计算 SHA256 并进行备份，这彻底杜绝了全项目无差别扫描与历史库膨胀。
3. **双向事务还原算法 (Bidirectional Transaction)**：
   在回退时，系统自动识别当前指针与目标快照的位置差，进行 **逆向撤销 (Undo)** 或 **正向重做 (Redo)**，只对本次快照追踪的相关文件进行物理新增/覆盖/删除，对项目的其他无关文件不做任何干扰。

---

## 命令行使用手册

你可以随时在终端运行此脚本进行手动版本控制：

### 1. 保存当前工作区快照
你可以使用 `--files` 显式指定本轮计划修改或新建的文件路径（空格分隔）。这是**强烈推荐**的做法，不仅执行极速，而且能避免元数据记录不必要的项目其他无关文件。
```bash
python scripts/checkpoint.py --workspace "." save -m "完成主页登录逻辑开发" --files "src/components/Login.vue" "server/auth.go"
```
*(注意：如果不加 `--files` 参数，脚本将自动根据 Git 变动状态 `git status` 抓取需要备份的文件，若无 Git 仓库则会自动收集最近 2 小时内被修改过的文本文件。)*

### 2. 查看快照历史记录列表
```bash
python scripts/checkpoint.py --workspace "." list
```

### 3. 查看当前代码与指定快照的差异 (Diff)
```bash
python scripts/checkpoint.py --workspace "." diff --id cp_1
```

### 4. 精确回退到指定快照状态
```bash
python scripts/checkpoint.py --workspace "." rollback --id cp_1
```

### 5. 裁剪历史快照并进行垃圾回收 (GC)
默认会自动裁剪并只保留最近的 **30次** 快照。超出该上限的历史快照元数据会被抹除，且没有任何快照引用的悬空文件会被物理删除以释放空间：
```bash
python scripts/checkpoint.py --workspace "." clean --keep 30
```

### 6. 彻底重置清空快照历史 (Reset)
物理删除所有快照记录，回到最干净的无记忆初始状态：
```bash
python scripts/checkpoint.py --workspace "." reset
```

---

## 🤖 AI 自动化安装提示词 (AI Auto-installation Prompt)

如果您在新的电脑、系统或全新的开发会话中需要使用此技能，可以直接复制以下提示词并发送给新的 AI 助手，它将**智能识别自身所在的 AI 平台**并自动将此工具配置为最适合它的运行环境：

```text
你是资深系统开发助手。现在我们需要在当前系统中安装一个全局或项目级的代码修改记忆与安全回退系统，用于在编写代码前自动备份，并在回滚时精准无损地物理还原。

第一步【自检并定位 AI 助手平台】：
请你首先智能识别你当前所在的 AI 助手/Agent 平台类型，并按照以下规则进行平台自适应安装：

1. 如果你是 Google Antigravity (IDE / CLI / Agent) 系列或 Gemini CLI (agy)：
   - 你的全局插件技能根目录在「家目录」下的 `.gemini\config\plugins\conversation-memory-plugin\skills\conversation_memory\`。
   - 提示：在 Windows 下你可以运行 PowerShell 命令 [System.Environment]::GetFolderPath('UserProfile') 或 Python 代码 import pathlib; print(pathlib.Path.home()) 来自动获取你当前的物理家目录绝对路径（如 C:\Users\<Username>）。在 macOS/Linux 下，家目录「~」即为 /Users/<Username>。
   - 目标文件：
     - 请将第二步获取到的 scripts/checkpoint.py 的源码写入：<全局插件目录>/scripts/checkpoint.py
     - 请将本提示词下方的「🚨 核心备份与安全回滚规则（SKILL.md 格式）」全文写入：<全局插件目录>/SKILL.md

2. 如果你是 Claude Code (Anthropic CLI)：
   - 你的全局配置文件在用户家目录下的 `.clauderc` 中。
   - 请在用户家目录下创建一个专用的工具目录（如 ~/.claude/tools/），并将第二步获取到的 scripts/checkpoint.py 源码原样写入其中。
   - 并将本提示词下方的「🚨 核心备份与安全回滚规则」以项目指令或全局规则的形式，追加写入到你的全局 `.clauderc` 配置文件或系统指令中。

3. 如果你是 Cursor、Windsurf 或 Copilot 等 IDE 内置的 AI Agent：
   - 你通过读取当前项目根目录下的本地 `.cursorrules` 文件来约束行为。
   - 请直接在用户当前目标开发项目的根目录下创建 `.cursorrules` 文件。
   - 并将本提示词下方的「🚨 核心备份与安全回滚规则」全文写入其中。同时提示用户将 scripts/checkpoint.py 的源码物理复制到他本地项目的 scripts/ 目录下以备运行。


第二步【网络下载核心脚本源码】：
请通过你的网络读取工具（或直接运行 git/curl 命令）拉取此工具远程 GitHub 仓库中 scripts/checkpoint.py 的代码内容：
- 仓库地址：https://github.com/weilimao/conversationMemorySkill.git
- 核心脚本源码直连 URL（你可以使用 read_url_content 等网络工具直接读取并加载其纯文本内容）：https://raw.githubusercontent.com/weilimao/conversationMemorySkill/main/scripts/checkpoint.py


第三步【落地配置文件与验证】：
请根据第一步中自检出的平台规范进行落地。

---
「🚨 核心备份与安全回滚规则」：

* 每次修改文件前的备份准则 (Save Checkpoint)
  在你执行任何代码修改（无论是主要功能开发，还是极细微的Bug修复与微调，如调用 replace_file_content, write_to_file, multi_replace_file_content 等）的前一步，你必须首先在终端运行保存快照指令，且必须使用 --files 参数显式指明你本轮计划修改或新建的特定文件相对路径：
  python "<checkpoint.py的安装路径>" --workspace "<当前工作区绝对路径>" save -m "<描述本次修改意图>" --files <本轮即将修改或新建的所有文件路径，空格分隔>

* 当用户要求回滚或撤销时 (Rollback)
  严禁自行人肉重写文件恢复！请按以下步骤操作：
  1. 运行 python "<checkpoint.py的安装路径>" --workspace "<当前工作区绝对路径>" list 列出快照。
  2. 找到目标 ID，运行 python "<checkpoint.py的安装路径>" --workspace "<当前工作区绝对路径>" rollback --id <checkpoint_id> 进行双向事务回滚。
  3. 报告回滚结果。
---

写入完成后，请尝试运行 save 命令创建一个 cp_1 快照进行测试，确认部署成功。
```

---

## 🚀 主流 AI 编辑器/Agent（Cursor / Claude Code / Windsurf / Copilot）项目级免安装适配

除了在 Antigravity 中作为全局插件安装外，本项目还支持在**主流 AI 编辑器/Agent 中零配置开箱即用**：

1. **Cursor & Windsurf**：
   本仓库根目录下已内置了 [`.cursorrules`](file:///e:/GPT/conversationMemorySkill/.cursorrules) 配置文件。当您使用 Cursor 或 Windsurf 打开本工程并进行 AI 编程时，编辑器会自动读取该规则。AI 助手将在每次帮您修改代码前自动保存 Checkpoint，在您要求回滚时自动执行恢复，无需进行任何全局安装！
2. **Claude Code**：
   Claude 会自动解析本工程的 [`.cursorrules`](file:///e:/GPT/conversationMemorySkill/.cursorrules)，或者您也可以将该规则直接复制作为项目的开发规则（`Instructions`），它就会在修改文件前调用本地 `python scripts/checkpoint.py save`。
3. **Copilot / Codex**：
   会自动识别本地规则文件，执行同等的安全防护。
