import os
import sys
import json
import hashlib
import shutil
import argparse
import difflib
from datetime import datetime
from pathlib import Path

# 定义默认忽略的文件夹和文件类型
IGNORE_DIRS = {
    ".git", ".gemini", "node_modules", "__pycache__", "venv", ".venv",
    "dist", "build", ".idea", ".vscode", "out", "target", ".history"
}

IGNORE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe", ".dll", ".so", ".dylib",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".mp4", ".mp3", ".pdf", ".db",
    ".pyc", ".o", ".a", ".lib", ".bin", ".class", ".war", ".ear"
}

def is_binary(file_path: Path) -> bool:
    """通过读取前1024字节判断是否为二进制文件"""
    if file_path.suffix.lower() in IGNORE_EXTS:
        return True
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
    except Exception:
        return True
    return False

def calculate_sha256(file_path: Path) -> str:
    """计算文件的 SHA256 哈希值"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

class CheckpointManager:
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path).resolve()
        self.meta_dir = self.workspace / ".gemini" / "checkpoints"
        self.store_dir = self.meta_dir / "store"
        self.metadata_path = self.meta_dir / "metadata.json"
        
        # 初始化目录
        self.store_dir.mkdir(parents=True, exist_ok=True)
        if not self.metadata_path.exists():
            self._save_metadata({"checkpoints": [], "current_checkpoint_id": None})

    def _load_metadata(self) -> dict:
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"checkpoints": [], "current_checkpoint_id": None}

    def _save_metadata(self, metadata: dict):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _get_managed_files(self) -> list[Path]:
        """递归扫描工作区中的所有有效文本代码文件"""
        managed_files = []
        for root, dirs, files in os.walk(self.workspace):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                # 排除隐藏文件
                if file.startswith("."):
                    continue
                # 判断是否为非二进制文件
                if not is_binary(file_path):
                    managed_files.append(file_path)
        return managed_files

    def save_checkpoint(self, description: str) -> str:
        """保存当前工作区的快照到版本库"""
        metadata = self._load_metadata()
        managed_files = self._get_managed_files()
        
        # 1. 构建当前 Manifest: 相对路径 -> SHA256 哈希
        current_manifest = {}
        for file_path in managed_files:
            rel_path = file_path.relative_to(self.workspace).as_posix()
            sha256 = calculate_sha256(file_path)
            current_manifest[rel_path] = sha256
            
            # 2. 如果 store 中没有该哈希的文件，物理拷贝到 store 目录中进行内容寻址存储
            store_file = self.store_dir / sha256
            if not store_file.exists():
                shutil.copy2(file_path, store_file)

        # 3. 对比上一个 checkpoint 计算增量差异 (added, modified, deleted)
        last_manifest = {}
        if metadata["checkpoints"]:
            last_manifest = metadata["checkpoints"][-1]["manifest"]

        added = []
        modified = []
        deleted = []

        # 找出修改或新增
        for rel_path, sha256 in current_manifest.items():
            if rel_path not in last_manifest:
                added.append(rel_path)
            elif last_manifest[rel_path] != sha256:
                modified.append(rel_path)
                
        # 找出删除
        for rel_path in last_manifest.keys():
            if rel_path not in current_manifest:
                deleted.append(rel_path)

        # 如果自上一个 checkpoint 以来没有任何变化，则不需要重复保存
        if not added and not modified and not deleted and metadata["checkpoints"]:
            print("工作区无任何文件变动，无需保存新 Checkpoint。")
            return metadata["current_checkpoint_id"]

        # 4. 生成新 checkpoint 实体
        cp_num = len(metadata["checkpoints"]) + 1
        cp_id = f"cp_{cp_num}"
        
        new_checkpoint = {
            "id": cp_id,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "manifest": current_manifest,
            "changes": {
                "added": added,
                "modified": modified,
                "deleted": deleted
            }
        }
        
        metadata["checkpoints"].append(new_checkpoint)
        metadata["current_checkpoint_id"] = cp_id
        self._save_metadata(metadata)
        
        print(f"成功保存快照 [{cp_id}]：{description}")
        print(f"变动概要: 新增 {len(added)}，修改 {len(modified)}，删除 {len(deleted)}")
        return cp_id

    def list_checkpoints(self):
        """展示历史 checkpoints"""
        metadata = self._load_metadata()
        checkpoints = metadata["checkpoints"]
        current_id = metadata["current_checkpoint_id"]
        
        if not checkpoints:
            print("暂无保存的历史 Checkpoint 快照。")
            return

        print("\n=== Checkpoint 历史快照列表 ===")
        for cp in checkpoints:
            prefix = "-> " if cp["id"] == current_id else "   "
            time_str = cp["timestamp"].split("T")[0] + " " + cp["timestamp"].split("T")[1][:8]
            changes = cp["changes"]
            summary = f"新增:{len(changes['added'])} | 修改:{len(changes['modified'])} | 删除:{len(changes['deleted'])}"
            print(f"{prefix}[{cp['id']}]  时间: {time_str}  描述: {cp['description']}  ({summary})")
        print("===============================\n")

    def rollback_to(self, checkpoint_id: str):
        """完全还原工作区状态到指定 checkpoint"""
        metadata = self._load_metadata()
        target_cp = next((cp for cp in metadata["checkpoints"] if cp["id"] == checkpoint_id), None)
        
        if not target_cp:
            print(f"错误: 未找到 ID 为 [{checkpoint_id}] 的 Checkpoint 快照。")
            return

        target_manifest = target_cp["manifest"]
        
        # 1. 扫描当前工作区所有被管理文件
        current_managed = self._get_managed_files()
        
        # 2. 清理：如果在当前工作区，但在目标 Manifest 中不存在（说明是后添加的），安全删除
        for file_path in current_managed:
            rel_path = file_path.relative_to(self.workspace).as_posix()
            if rel_path not in target_manifest:
                try:
                    file_path.unlink()
                    print(f"删除新增文件: {rel_path}")
                except Exception as e:
                    print(f"警告: 无法删除文件 {rel_path} - {e}")

        # 3. 恢复/覆盖：如果目标 Manifest 中的文件在工作区不存在或哈希不一致，从 store 中拷出恢复
        for rel_path, expected_sha in target_manifest.items():
            dest_path = self.workspace / rel_path
            store_file = self.store_dir / expected_sha
            
            if not store_file.exists():
                print(f"致命错误: 无法在版本库中找到哈希为 {expected_sha} 的备份文件 ({rel_path})。")
                continue
            
            # 判断是否需要覆盖
            need_restore = False
            if not dest_path.exists():
                need_restore = True
            else:
                current_sha = calculate_sha256(dest_path)
                if current_sha != expected_sha:
                    need_restore = True
            
            if need_restore:
                try:
                    # 确保父目录存在
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(store_file, dest_path)
                    print(f"恢复/更新文件: {rel_path}")
                except Exception as e:
                    print(f"错误: 无法恢复文件 {rel_path} - {e}")

        # 4. 更新当前的 checkpoint 指针
        metadata["current_checkpoint_id"] = checkpoint_id
        self._save_metadata(metadata)
        print(f"\n工作区已成功回滚到 [{checkpoint_id}]：{target_cp['description']}")

    def diff_checkpoint(self, checkpoint_id: str):
        """对比当前工作区状态与指定 checkpoint 的差异，打印 unified diff"""
        metadata = self._load_metadata()
        target_cp = next((cp for cp in metadata["checkpoints"] if cp["id"] == checkpoint_id), None)
        
        if not target_cp:
            print(f"错误: 未找到 ID 为 [{checkpoint_id}] 的 Checkpoint 快照。")
            return

        target_manifest = target_cp["manifest"]
        current_files = {file_path.relative_to(self.workspace).as_posix(): file_path 
                         for file_path in self._get_managed_files()}

        diff_found = False

        # 对比 Manifest 中的文件
        for rel_path, target_sha in target_manifest.items():
            store_file = self.store_dir / target_sha
            target_lines = []
            if store_file.exists():
                try:
                    with open(store_file, "r", encoding="utf-8", errors="ignore") as f:
                        target_lines = f.readlines()
                except Exception:
                    pass

            if rel_path in current_files:
                current_file_path = current_files[rel_path]
                current_sha = calculate_sha256(current_file_path)
                if current_sha != target_sha:
                    # 文件被修改了，输出 diff
                    diff_found = True
                    try:
                        with open(current_file_path, "r", encoding="utf-8", errors="ignore") as f:
                            current_lines = f.readlines()
                        diff = difflib.unified_diff(
                            target_lines, current_lines,
                            fromfile=f"[{checkpoint_id}] {rel_path}",
                            tofile=f"[当前工作区] {rel_path}"
                        )
                        print("".join(diff))
                    except Exception as e:
                        print(f"无法对比文件 {rel_path} 的差异: {e}")
            else:
                # 文件被删除了
                diff_found = True
                print(f"\n- 已删除的文件: {rel_path}")
                for line in target_lines:
                    print(f"- {line.rstrip()}")

        # 检查哪些文件是新加的
        for rel_path, current_file_path in current_files.items():
            if rel_path not in target_manifest:
                diff_found = True
                print(f"\n+ 新增的文件: {rel_path}")
                try:
                    with open(current_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            print(f"+ {line.rstrip()}")
                except Exception:
                    pass

        if not diff_found:
            print("当前工作区与该 Checkpoint 完全一致，无任何差异。")

def main():
    parser = argparse.ArgumentParser(description="Antigravity 智能会话修改记忆与回滚工具")
    parser.add_argument("--workspace", default=".", help="工作区根目录路径")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # save 子命令
    save_parser = subparsers.add_parser("save", help="保存当前状态")
    save_parser.add_argument("-m", "--message", required=True, help="对当前修改状态的描述信息")
    
    # list 子命令
    subparsers.add_parser("list", help="列出历史 checkpoint 快照")
    
    # rollback 子命令
    rollback_parser = subparsers.add_parser("rollback", help="回滚至指定快照")
    rollback_parser.add_argument("--id", required=True, help="快照的ID，如 cp_1")
    
    # diff 子命令
    diff_parser = subparsers.add_parser("diff", help="展示当前工作区与指定快照的差异")
    diff_parser.add_argument("--id", required=True, help="快照的ID，如 cp_1")
    
    args = parser.parse_args()
    
    # 实例化 Manager 并运行命令
    manager = CheckpointManager(args.workspace)
    
    if args.command == "save":
        manager.save_checkpoint(args.message)
    elif args.command == "list":
        manager.list_checkpoints()
    elif args.command == "rollback":
        manager.rollback_to(args.id)
    elif args.command == "diff":
        manager.diff_checkpoint(args.id)

if __name__ == "__main__":
    main()
