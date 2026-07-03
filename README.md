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
默认会自动裁剪并只保留最近的 **30次** 快照。超出该上限的历史快照元数据会被抹除，且没有任何快照引用的悬向文件会被物理删除以释放空间：
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

如果您在新的电脑、系统或全新的开发会话中需要使用此技能，可以直接复制以下提示词并发送给新的 AI 助手，它将自动将此工具配置为全局可用的插件：

```text
你是资深系统开发助手。现在我们需要在当前系统中安装一个全局的 Antigravity 技能，用于对代码进行精准的备份快照管理与安全回滚。

第一步：请你首先根据当前的操作系统，动态定位全局插件技能的安装路径：
- Windows系统下：全局插件 Skill 安装根目录在「家目录」下的 `.gemini\config\plugins\conversation-memory-plugin\skills\conversation_memory\`。请运行 PowerShell 命令 [System.Environment]::GetFolderPath('UserProfile') 或 Python 代码 import pathlib; print(pathlib.Path.home()) 来自动获取你当前的物理家目录路径（通常格式为 C:\Users\<Username>）。
- macOS/Linux系统下：全局插件 Skill 安装根目录在「~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/」。其中「~」即为你的用户家目录（通常格式为 /Users/<Username>）。

第二步：请通过你的网络读取工具（或直接运行 git/curl 命令）拉取此工具远程 GitHub 仓库中 scripts/checkpoint.py 的代码内容：
- 仓库地址：https://github.com/weilimao/conversationMemorySkill.git
- 核心脚本源码直连 URL（你可以使用 read_url_content 等网络工具直接读取并加载其纯文本内容）：https://raw.githubusercontent.com/weilimao/conversationMemorySkill/main/scripts/checkpoint.py

第三步：请通过你拥有的 write_to_file 或 shell 写入工具，在对应系统的全局路径中创建这两个文件：

1. 脚本路径：<第一步获取到的全局安装目录>/scripts/checkpoint.py
   内容：请将第二步拉取到的 scripts/checkpoint.py 的源码原样写入。

2. 规则路径：<第一步获取到的全局安装目录>/SKILL.md
   内容：写入以下 YAML 及 Markdown 配置：
---
name: conversation_memory
description: >
  CRITICAL: Always call this skill to save a checkpoint before you modify/create/delete any files in the workspace. Also use this skill's rollback command to restore files to a previous state when the user requests to revert or undo changes.
---

# 智能代码记忆与安全回退技能 (Conversation Memory)

## 技能说明
在长会话开发中，你（AI助手）会对代码进行多次修改。为了保障用户的代码安全，防止因为多次修改后回退失败导致代码大范围丢失或错乱，**你必须严格遵守本技能的行为规范。**

> [!IMPORTANT]
> **硬性红线 (HARD RED LINE)**：
> 1. 在你执行任何代码修改（无论是主要功能实现，还是极细微的Bug修复与微调，如调用 `replace_file_content`, `write_to_file`, `multi_replace_file_content` 等）的**前一步**，你**必须首先**在终端运行保存快照指令。
> 2. 必须且只能通过 `--files` 参数指定 you本轮计划修改或新建的那些文件。严禁进行全盘无差别备份，从而防止磁盘空间膨胀！

---

## 行为规范指引

### 1. 修改代码前的备份准则 (Save Checkpoint)
当你确认了修改意图，准备对工作区内的某些文件进行写操作前，**立刻在终端执行如下保存命令**，把这几个文件在修改前的原始状态备份下来：

```powershell
python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<当前工作区绝对路径>" save -m "<描述本次修改意图>" --files <本轮即将修改或新建的所有文件路径，空格分隔>
```

*例如，如果你准备进行第二轮修改，微调 `src/main.py` 和新增 `tests/test_api.py`，你必须在写文件前执行：*
```powershell
python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "e:/GPT/conversationMemorySkill" save -m "第二次微调：增加API校验与单元测试" --files "src/main.py" "tests/test_api.py"
```
*这会确保如果本次修改改错了，我们能够 100% 精准地将这两个文件回退到这一步之前的样子，而绝不干扰项目的其他无关部分！*

### 2. 回退与恢复准则 (List & Rollback Checkpoint)
当用户对修改不满意，提出回退要求时，你必须按以下步骤操作：

#### 步骤一：列出所有已保存的 Checkpoints
在终端运行以下指令，查看该工作区的历史快照列表：
```powershell
python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<当前工作区绝对路径>" list
```

#### 步骤二：对比差异（可选）
如果对要回滚到哪个版本不够确定，可以运行 `diff` 指令对比当前状态与目标快照的差异：
```powershell
python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<当前工作区绝对路径>" diff --id <checkpoint_id>
```

#### 步骤三：执行精准回滚
找到用户所期望的那个 Checkpoint ID（如 `cp_2`）后，在终端执行以下指令将工作区中本快照追踪的文件一键回退到备份时的原始状态：
```powershell
python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<当前工作区绝对路径>" rollback --id <checkpoint_id>
```

#### 步骤四：告知用户结果
回退成功后，向用户汇报已成功退回至指定版本，并简单列出被恢复和清理的文件。

### 3. 历史快照的磁盘垃圾清理准则 (Clean & GC)
- 为了防止长期的历史快照无限累积从而占满用户磁盘空间，你应当有意识地对备份库进行清理。
- 当在 `list` 发现快照节点数较多，或者当用户主动要求“帮我清理一下旧快照”时，你应该在终端运行垃圾回收指令，默认裁剪历史并保留最近的 **30次** 快照：
  ```powershell
  python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<当前工作区绝对路径>" clean --keep 30
  ```
- **注意**：如果用户要求彻底重置/清空所有快照历史，你应当在终端运行重置命令：
  ```powershell
  python "~/.gemini/config/plugins/conversation-memory-plugin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<当前工作区绝对路径>" reset
  ```
```

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
