# 智能代码记忆与安全回退工具 (Conversation Memory)

本项目为 Google Antigravity 系统定制开发了一个智能记忆与代码精准回退的全局 Skill 工具。
它主要用于在 AI 进行多轮代码修改时，通过在物理上为当前修改做快照，从而在用户说“改得不对，退回到第二次修改”等恢复要求时，能通过历史快照列表**100%精准无损地**回滚代码，有效防止 AI 乱改乱恢复的问题。

---

## 目录结构
```text
e:\GPT\conversationMemorySkill\
├── scripts/
│   └── checkpoint.py      # 本地版本管理核心 Python 脚本
└── README.md              # 项目使用说明书
```

---

## 核心机制：内容寻址存储（CAS）
与普通的简单目录打包备份不同，本工具借鉴了 Git 底层数据库的设计精髓：
1. **去重存储**：备份文件以内容的 SHA256 哈希值作为文件名存储在 `.gemini/checkpoints/store/<sha256>` 下。相同内容的文件无论属于哪个版本，在磁盘上都只占用一份空间。
2. **状态快照 (Manifest)**：每一个 checkpoint 快照仅仅记录一份元数据 Manifest（映射了每一个相对路径对应的 SHA256 值）。
3. **安全清理**：在回滚时，程序会自动计算目标版本的 Manifest，自动恢复被改动或删除的文件，并自动清理在当前版本中多余的新增文件。

---

## 命令行使用手册

你可以随时在终端运行此脚本进行手动版本控制：

### 1. 保存当前工作区快照
```bash
python scripts/checkpoint.py --workspace "." save -m "完成主页登录逻辑开发"
```

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
默认会自动裁剪并只保留最近的 **30 次** 快照。超出该上限的历史快照元数据会被抹除，且没有任何快照引用的悬空文件会被物理删除以释放空间：
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

如果您在新的电脑、系统或全新的开发会话中需要使用此技能，可以直接复制以下提示词并发送给新的 AI 助手，它将自动将此工具配置为全局可用的 Skill：

```text
你是资深系统开发助手。现在我们需要在当前系统中安装一个全局的 Antigravity 技能，用于对代码进行精准的备份快照管理与安全回滚。

第一步：请你首先根据当前的操作系统，动态定位全局技能的安装路径：
- Windows系统下：全局 Skill 安装根目录在「家目录」下的 `.gemini\antigravity\builtin\skills\conversation_memory\`。请运行 PowerShell 命令 [System.Environment]::GetFolderPath('UserProfile') 或 Python 代码 import pathlib; print(pathlib.Path.home()) 来自动获取你当前的物理家目录路径（通常格式为 C:\Users\<Username>）。
- macOS/Linux系统下：全局 Skill 安装根目录在「~/.gemini/antigravity/builtin/skills/conversation_memory/」。其中「~」即为你的用户家目录（通常格式为 /Users/<Username>）。

第二步：请通过你的网络读取工具（或直接运行 git/curl 命令）拉取此工具远程 GitHub 仓库中 scripts/checkpoint.py 的代码内容：
- 仓库地址：https://github.com/weilimao/conversationMemorySkill.git
- 核心脚本源码直连 URL（你可以使用 read_url_content 等网络工具直接读取并加载其纯文本内容）：https://raw.githubusercontent.com/weilimao/conversationMemorySkill/main/scripts/checkpoint.py

第三步：请通过你拥有的 write_to_file 或 shell 写入工具，在对应系统的全局路径中创建这两个文件：

1. 脚本路径：<第一步获取到的全局安装目录>/scripts/checkpoint.py
   内容：请将第二步拉取到的 scripts/checkpoint.py 的源码原样写入。

2. 规则路径：<第一步获取到的全局安装目录>/SKILL.md
   内容：请全文写入以下 YAML 及 Markdown 配置：
---
name: conversation_memory
description: >
  CRITICAL: Always call this skill to save a checkpoint before you modify/create/delete any files in the workspace. Also use this skill's rollback command to restore files to a previous state when the user requests to revert or undo changes.
---

# 智能代码记忆与安全回退技能 (Conversation Memory)

## 技能说明
在长会话开发中，为避免回退出错，修改或新建工作区文件前，必须先在终端运行：
python "~/.gemini/antigravity/builtin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<工作区绝对路径>" save -m "<修改内容的清晰总结>"

用户要求回退时，先运行：
python "~/.gemini/antigravity/builtin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<工作区绝对路径>" list

找到对应的 ID 运行：
python "~/.gemini/antigravity/builtin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<工作区绝对路径>" rollback --id <checkpoint_id>

严禁自行人肉重写文件恢复！
```


*💡 **Windows 下的家目录定位指引**：在 Windows 上，请运行 PowerShell 命令 `[System.Environment]::GetFolderPath('UserProfile')` 或执行 Python 代码 `import pathlib; print(pathlib.Path.home())` 来获取你当前所处 Windows 系统的真实用户家目录绝对路径（通常格式为 `C:\Users\<您的用户名>`），随后在 `<家目录>\.gemini\antigravity\builtin\skills\conversation_memory\` 下部署上述文件即可。对于 macOS 电脑，家目录（`~`）即为 `/Users/<您的用户名>`。*

写入完成后，请尝试运行 save 命令创建一个 cp_1 快照进行测试，确认部署成功。
```

---

## 🚀 主流 AI 编辑器/Agent（Cursor / Claude Code / Windsurf / Copilot）项目级免安装适配

除了在 Antigravity 中作为全局 Skill 安装外，本项目还支持在**主流 AI 编辑器/Agent 中零配置开箱即用**：

1. **Cursor & Windsurf**：
   本仓库根目录下已内置了 [`.cursorrules`](file:///e:/GPT/conversationMemorySkill/.cursorrules) 配置文件。当您使用 Cursor 或 Windsurf 打开本工程并进行 AI 编程时，编辑器会自动读取该规则。AI 助手将在每次帮您修改代码前自动保存 Checkpoint，在您要求回滚时自动执行恢复，无需进行任何全局安装！
2. **Claude Code**：
   Claude 会自动解析本工程的 [`.cursorrules`](file:///e:/GPT/conversationMemorySkill/.cursorrules)，或者您也可以将该规则直接复制作为项目的开发规则（`Instructions`），它就会在修改文件前调用本地 `python scripts/checkpoint.py save`。
3. **Copilot / Codex**：
   会自动识别本地规则文件，执行同等的安全防护。


