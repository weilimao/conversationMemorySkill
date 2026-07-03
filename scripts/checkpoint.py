import os
import sys
import json
import hashlib
import shutil
import argparse
import difflib
import subprocess
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

    def _get_git_changed_files(self) -> list[Path]:
        """通过 git status 获取当前有变动的文件列表"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            changed = []
            for line in result.stdout.splitlines():
                if len(line) > 3:
                    # 获取文件相对路径并去除可能存在的引号
                    rel_path = line[3:].strip()
                    if rel_path.startswith('"') and rel_path.endswith('"'):
                        rel_path = rel_path[1:-1]
                        try:
                            # 尝试对 octal 字符转义进行 decode
                            rel_path = rel_path.encode('utf-8').decode('unicode_escape')
                        except Exception:
                            pass
                    file_path = self.workspace / rel_path
                    changed.append(file_path)
            return changed
        except Exception:
            return []

    def _get_recently_modified_files(self) -> list[Path]:
        """局部扫描：获取最近两小时内修改过的文本文件列表"""
        import time
        changed = []
        two_hours_ago = time.time() - 7200
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            root_path = Path(root)
            for file in files:
                if file.startswith("."):
                    continue
                file_path = root_path / file
                if file_path.suffix.lower() in IGNORE_EXTS:
                    continue
                try:
                    mtime = file_path.stat().st_mtime
                    if mtime > two_hours_ago and not is_binary(file_path):
                        changed.append(file_path)
                except Exception:
                    pass
        return changed

    def save_checkpoint(self, description: str, files: list[str] = None) -> str:
        """保存被指定的、或被修改的代码文件状态到快照中"""
        metadata = self._load_metadata()
        
        # 1. 搜集需要保存快照的目标文件列表
        target_files = []
        if files:
            for f in files:
                f_path = Path(self.workspace / f).resolve()
                # 即使文件在本地还未被创建，我们也需要记录它以便回滚时删除
                target_files.append(f_path)
        else:
            # 自动探测：优先使用 git changed files
            git_files = self._get_git_changed_files()
            if git_files:
                target_files = git_files
            else:
                # 兜底：获取两小时内修改过的文本文件
                target_files = self._get_recently_modified_files()

        if not target_files:
            print("当前工作区无任何文件发生改变，且未传入任何需要追踪的文件，无需保存 Checkpoint。")
            return metadata["current_checkpoint_id"]

        # 2. 对目标文件进行哈希比对与内容物理备份
        current_manifest = {}
        added = []
        modified = []
        deleted = []

        last_manifest = {}
        if metadata["checkpoints"]:
            last_manifest = metadata["checkpoints"][-1].get("manifest", {})

        for file_path in target_files:
            try:
                rel_path = file_path.relative_to(self.workspace).as_posix()
            except Exception:
                continue

            if file_path.exists() and not is_binary(file_path):
                sha256 = calculate_sha256(file_path)
                current_manifest[rel_path] = sha256
                
                # 去重复制备份到 store 文件夹中
                store_file = self.store_dir / sha256
                if not store_file.exists():
                    shutil.copy2(file_path, store_file)

                # 判断文件的具体变动类型 (added, modified)
                if rel_path not in last_manifest:
                    added.append(rel_path)
                elif last_manifest[rel_path] != sha256:
                    modified.append(rel_path)
            else:
                # 文件不存在，说明被删除了，或者即将被新建
                if rel_path in last_manifest:
                    deleted.append(rel_path)
                else:
                    added.append(rel_path)

        # 3. 如果通过自动探测并没有任何增量文件变化，则直接静默退出不创建无用节点
        if not added and not modified and not deleted and not files:
            print("工作区无增量文件变动，直接拦截，静默退出。")
            return metadata["current_checkpoint_id"]

        # 4. 固化快照元数据
        cp_num = len(metadata["checkpoints"]) + 1
        cp_id = f"cp_{cp_num}"
        
        new_checkpoint = {
            "id": cp_id,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "manifest": current_manifest, # 极精简 Manifest：只记录在这个快照中被修改或显式追踪的文件路径和哈希
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
        print(f"追踪备份文件: {', '.join(current_manifest.keys())}")
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

    def _restore_file(self, rel_path: str, sha256: str):
        dest_path = self.workspace / rel_path
        store_file = self.store_dir / sha256
        if store_file.exists():
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(store_file, dest_path)
                print(f" 恢复/更新文件: {rel_path}")
            except Exception as e:
                print(f" 无法恢复文件 {rel_path} - {e}")
        else:
            print(f" 致命错误: 版本库中缺失哈希为 {sha256} 的文件 ({rel_path})")

    def rollback_to(self, checkpoint_id: str):
        """双向事务机制：将工作区代码状态精确还原到指定的快照版本"""
        metadata = self._load_metadata()
        checkpoints = metadata["checkpoints"]
        
        target_idx = next((i for i, cp in enumerate(checkpoints) if cp["id"] == checkpoint_id), None)
        if target_idx is None:
            print(f"错误: 未找到 ID 为 [{checkpoint_id}] 的 Checkpoint 快照。")
            return

        current_id = metadata["current_checkpoint_id"]
        # 如果当前指针无效，默认指向最新一个
        current_idx = next((i for i, cp in enumerate(checkpoints) if cp["id"] == current_id), len(checkpoints) - 1)

        if current_idx < target_idx:
            # 1. 向未来的较新版本前进 (Redo)
            print(f"正在向未来快照 [{checkpoint_id}] 推进恢复...")
            for i in range(current_idx + 1, target_idx + 1):
                cp = checkpoints[i]
                manifest = cp["manifest"]
                changes = cp["changes"]
                
                # 重新应用该版本下新增或被修改的文件
                for rel_path in changes["added"] + changes["modified"]:
                    if rel_path in manifest:
                        self._restore_file(rel_path, manifest[rel_path])
                # 重新物理删除在未来版本中被删除的文件
                for rel_path in changes["deleted"]:
                    dest_path = self.workspace / rel_path
                    if dest_path.exists():
                        try:
                            dest_path.unlink()
                            print(f" 删除文件: {rel_path}")
                        except Exception as e:
                            print(f" 无法删除文件 {rel_path} - {e}")
        else:
            # 2. 向历史的较旧版本回撤 (Undo)
            print(f"正在向历史快照 [{checkpoint_id}] 回撤修改...")
            for i in range(current_idx, target_idx, -1):
                cp = checkpoints[i]
                manifest = cp["manifest"]
                changes = cp["changes"]
                
                # 撤销新增：物理删除新加的文件
                for rel_path in changes["added"]:
                    dest_path = self.workspace / rel_path
                    if dest_path.exists():
                        try:
                            dest_path.unlink()
                            print(f" 撤销新增(物理删除): {rel_path}")
                        except Exception as e:
                            print(f" 无法删除文件 {rel_path} - {e}")
                
                # 撤销修改和删除：将文件回滚还原为当前快照中记录的前置（修改前）哈希内容
                for rel_path in changes["modified"] + changes["deleted"]:
                    if rel_path in manifest:
                        self._restore_file(rel_path, manifest[rel_path])
                    else:
                        # 说明在更早的历史里该文件也是不存在的，直接执行删除
                        dest_path = self.workspace / rel_path
                        if dest_path.exists():
                            dest_path.unlink()

        # 更新指针
        metadata["current_checkpoint_id"] = checkpoint_id
        self._save_metadata(metadata)
        print(f"\n工作区状态成功还原至 [{checkpoint_id}]：{checkpoints[target_idx]['description']}")

    def diff_checkpoint(self, checkpoint_id: str):
        """对比当前工作区状态与指定 checkpoint 的差异，打印 unified diff"""
        metadata = self._load_metadata()
        target_cp = next((cp for cp in metadata["checkpoints"] if cp["id"] == checkpoint_id), None)
        
        if not target_cp:
            print(f"错误: 未找到 ID 为 [{checkpoint_id}] 的 Checkpoint 快照。")
            return

        target_manifest = target_cp["manifest"]
        
        # 扫描当前被快照追踪管理的相关文件
        current_files = {}
        for rel_path in target_manifest.keys():
            file_path = self.workspace / rel_path
            if file_path.exists():
                current_files[rel_path] = file_path

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
                diff_found = True
                print(f"\n- 已删除的文件: {rel_path}")
                for line in target_lines:
                    print(f"- {line.rstrip()}")

        if not diff_found:
            print("当前工作区与该 Checkpoint 指定追踪的文件状态完全一致，无任何差异。")

    def clean_checkpoints(self, keep_count: int) -> int:
        """裁剪历史快照，并对未引用的备份文件进行垃圾回收(GC)"""
        metadata = self._load_metadata()
        checkpoints = metadata["checkpoints"]
        
        if len(checkpoints) <= keep_count:
            print(f"当前快照数({len(checkpoints)})未超过保留上限({keep_count})，无需清理。")
            return 0
            
        num_to_remove = len(checkpoints) - keep_count
        removed_cps = checkpoints[:num_to_remove]
        keep_cps = checkpoints[num_to_remove:]
        
        # 1. 统计所有被保留快照引用的 SHA256 哈希值
        referenced_hashes = set()
        for cp in keep_cps:
            referenced_hashes.update(cp["manifest"].values())
            
        # 2. 物理删除不再被任何快照引用的 store 文件 (Garbage Collection)
        deleted_files_count = 0
        for file in self.store_dir.iterdir():
            if file.is_file() and file.name not in referenced_hashes:
                try:
                    file.unlink()
                    deleted_files_count += 1
                except Exception as e:
                    print(f"警告: 无法回收悬空文件 {file.name} - {e}")
                    
        # 3. 更新 metadata 并写回
        metadata["checkpoints"] = keep_cps
        keep_ids = {cp["id"] for cp in keep_cps}
        if metadata["current_checkpoint_id"] not in keep_ids and keep_cps:
            metadata["current_checkpoint_id"] = keep_cps[-1]["id"]
            
        self._save_metadata(metadata)
        
        print(f"已成功裁剪前 {num_to_remove} 个历史快照。")
        print(f"垃圾回收成功：物理清除了 {deleted_files_count} 个悬空备份文件。当前快照保留数量: {len(keep_cps)}。")
        return deleted_files_count

    def reset_repository(self):
        """完全清除所有的快照与备份历史"""
        if self.meta_dir.exists():
            try:
                shutil.rmtree(self.meta_dir)
                print("已成功清空所有的快照数据库及备份文件实体。")
            except Exception as e:
                print(f"错误: 无法重置版本库 - {e}")
        else:
            print("当前没有找到任何版本库，无需重置。")

def main():
    parser = argparse.ArgumentParser(description="Antigravity 智能会话修改记忆与回退工具")
    parser.add_argument("--workspace", default=".", help="工作区根目录路径")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # save 子命令
    save_parser = subparsers.add_parser("save", help="保存当前状态")
    save_parser.add_argument("-m", "--message", required=True, help="对当前修改状态的描述信息")
    save_parser.add_argument("--files", nargs="*", help="本轮需要追踪备份的文件列表（相对路径）")
    
    # list 子命令
    subparsers.add_parser("list", help="列出历史 checkpoint 快照")
    
    # rollback 子命令
    rollback_parser = subparsers.add_parser("rollback", help="回滚至指定快照")
    rollback_parser.add_argument("--id", required=True, help="快照的ID，如 cp_1")
    
    # diff 子命令
    diff_parser = subparsers.add_parser("diff", help="展示当前工作区与指定快照的差异")
    diff_parser.add_argument("--id", required=True, help="快照的ID，如 cp_1")
    
    # clean 子命令
    clean_parser = subparsers.add_parser("clean", help="裁剪历史快照并进行垃圾回收(GC)")
    clean_parser.add_argument("--keep", type=int, default=30, help="要保留的最新快照数量，默认30次")
    
    # reset 子命令
    subparsers.add_parser("reset", help="彻底清空当前工作区的所有快照和备份实体")
    
    args = parser.parse_args()
    
    manager = CheckpointManager(args.workspace)
    
    if args.command == "save":
        manager.save_checkpoint(args.message, args.files)
    elif args.command == "list":
        manager.list_checkpoints()
    elif args.command == "rollback":
        manager.rollback_to(args.id)
    elif args.command == "diff":
        manager.diff_checkpoint(args.id)
    elif args.command == "clean":
        manager.clean_checkpoints(args.keep)
    elif args.command == "reset":
        manager.reset_repository()

if __name__ == "__main__":
    main()
