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

---

## 🤖 AI 自动化安装提示词 (AI Auto-installation Prompt)

如果您在新的电脑、系统或开发会话中需要使用此技能，可以直接复制以下提示词并发送给新的 AI 助手，它将自动将此工具配置为全局可用的 Skill：

```text
你是资深系统开发助手。现在我们需要在当前系统中安装一个全局的 Antigravity 技能，用于对代码进行精准的备份快照管理与安全回滚。
请通过你拥有的 write_to_file/shell 工具，在以下全局路径中创建这两个文件，代码直接提取自我当前项目工作区：

1. 路径：C:\Users\韦礼貌\.gemini\antigravity\builtin\skills\conversation_memory\scripts\checkpoint.py
   内容：请将我工作区下 scripts/checkpoint.py 的完整代码原样写入其中。

2. 路径：C:\Users\韦礼貌\.gemini\antigravity\builtin\skills\conversation_memory\SKILL.md
   内容：请全文写入以下 YAML 及 Markdown 配置：
---
name: conversation_memory
description: >
  CRITICAL: Always call this skill to save a checkpoint before you modify/create/delete any files in the workspace. Also use this skill's rollback command to restore files to a previous state when the user requests to revert or undo changes.
---

# 智能代码记忆与安全回退技能 (Conversation Memory)

## 技能说明
在长会话开发中，为避免回退出错，修改或新建工作区文件前，必须先在终端运行：
python "C:/Users/韦礼貌/.gemini/antigravity/builtin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<工作区绝对路径>" save -m "<修改内容的清晰总结>"

用户要求回退时，先运行：
python "C:/Users/韦礼貌/.gemini/antigravity/builtin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<工作区绝对路径>" list

找到对应的 ID 运行：
python "C:/Users/韦礼貌/.gemini/antigravity/builtin/skills/conversation_memory/scripts/checkpoint.py" --workspace "<工作区绝对路径>" rollback --id <checkpoint_id>

严禁自行人肉重写文件恢复！
```

写入完成后，请尝试运行 save 命令创建一个 cp_1 快照进行测试，确认部署成功。
```

