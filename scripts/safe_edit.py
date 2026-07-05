import os
import sys
import argparse
import subprocess
from pathlib import Path

def run_backup(workspace, session, message, file_path):
    # 动态寻找 checkpoint.py 的路径
    # 优先找与 safe_edit.py 同目录的 checkpoint.py
    script_dir = Path(__file__).parent
    checkpoint_script = script_dir / "checkpoint.py"
    
    if not checkpoint_script.exists():
        # 兜底寻找全局插件目录下的 checkpoint.py
        global_path = Path.home() / ".gemini" / "config" / "plugins" / "conversation-memory-plugin" / "skills" / "conversation_memory" / "scripts" / "checkpoint.py"
        if global_path.exists():
            checkpoint_script = global_path
        else:
            print(f"Error: checkpoint.py not found at {checkpoint_script} or {global_path}", file=sys.stderr)
            return False

    cmd = [
        sys.executable,
        str(checkpoint_script),
        "--workspace", str(workspace),
    ]
    if session:
        cmd.extend(["--session", session])
    
    cmd.extend([
        "save",
        "-m", message,
        "--files", file_path
    ])
    
    print(f"Executing backup command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        print(f"Backup failed (exit code: {result.returncode})", file=sys.stderr)
        try:
            print(f"Stdout: {result.stdout}", file=sys.stderr)
            print(f"Stderr: {result.stderr}", file=sys.stderr)
        except UnicodeEncodeError:
            encoding = sys.stderr.encoding or 'gbk'
            safe_stdout = result.stdout.encode(encoding, errors='replace').decode(encoding)
            safe_stderr = result.stderr.encode(encoding, errors='replace').decode(encoding)
            print(f"Stdout: {safe_stdout}", file=sys.stderr)
            print(f"Stderr: {safe_stderr}", file=sys.stderr)
        return False
    
    try:
        print(f"Backup succeeded.\n{result.stdout}")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'gbk'
        safe_stdout = result.stdout.encode(encoding, errors='replace').decode(encoding)
        print(f"Backup succeeded.\n{safe_stdout}")
    return True

def apply_edit(workspace, file_path, mode, target, replacement, overwrite=False):
    target_abs_path = (Path(workspace) / file_path).resolve()
    
    if mode == "write":
        target_abs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_abs_path, 'w', encoding='utf-8') as f:
            f.write(replacement)
        print(f"Successfully wrote new content to {file_path}")
        return True

    elif mode == "replace":
        if not target_abs_path.exists():
            print(f"Error: Target file {file_path} does not exist.", file=sys.stderr)
            return False
            
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'utf-16']
        content = None
        used_encoding = 'utf-8'
        for enc in encodings:
            try:
                with open(target_abs_path, 'r', encoding=enc) as f:
                    content = f.read()
                used_encoding = enc
                break
            except UnicodeDecodeError:
                continue
                
        if content is None:
            print(f"Error: Could not decode target file {file_path} with standard encodings.", file=sys.stderr)
            return False
            
        if target not in content:
            print("Error: Target content not found in target file. Cannot perform replace.", file=sys.stderr)
            # 打印部分调试信息，以便于AI知道哪里对不上
            print(f"--- Expected Target (Length: {len(target)}) ---", file=sys.stderr)
            print(target, file=sys.stderr)
            print("---------------------------------------------", file=sys.stderr)
            return False
            
        new_content = content.replace(target, replacement, 1)
        with open(target_abs_path, 'w', encoding=used_encoding) as f:
            f.write(new_content)
        print(f"Successfully replaced content in {file_path} using encoding: {used_encoding}")
        return True
    
    else:
        print(f"Error: Unknown mode {mode}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Antigravity Atomic Write and Auto Backup Proxy")
    parser.add_argument("--workspace", default=".", help="Workspace path")
    parser.add_argument("--session", default=None, help="Current session ID")
    parser.add_argument("--file", required=True, help="Relative path of file to edit")
    parser.add_argument("--message", required=True, help="Commit message for the backup checkpoint")
    parser.add_argument("--mode", choices=["replace", "write"], required=True, help="Edit mode")
    
    # 允许通过命令行传参，也可以通过临时文件传参
    parser.add_argument("--target", default="", help="Target content to be replaced (for replace mode)")
    parser.add_argument("--replacement", default="", help="Replacement content")
    
    parser.add_argument("--target-from-file", default=None, help="Path to temp file containing target content")
    parser.add_argument("--replacement-from-file", default=None, help="Path to temp file containing replacement content")
    
    args = parser.parse_args()
    
    workspace = Path(args.workspace).resolve()
    
    # 解析 target 与 replacement 内容
    target_content = args.target
    if args.target_from_file:
        try:
            with open(args.target_from_file, 'r', encoding='utf-8') as f:
                target_content = f.read()
        except Exception as e:
            print(f"Error reading target from file {args.target_from_file}: {e}", file=sys.stderr)
            sys.exit(1)
            
    replacement_content = args.replacement
    if args.replacement_from_file:
        try:
            with open(args.replacement_from_file, 'r', encoding='utf-8') as f:
                replacement_content = f.read()
        except Exception as e:
            print(f"Error reading replacement from file {args.replacement_from_file}: {e}", file=sys.stderr)
            sys.exit(1)
            
    # 1. 前置安全备份
    print("Initiating pre-write backup check...")
    if not run_backup(workspace, args.session, args.message, args.file):
        print("Backup check failed. Aborting write operation to prevent data loss.", file=sys.stderr)
        sys.exit(1)
        
    # 2. 物理写入/替换
    print("Backup verified. Applying modifications...")
    if not apply_edit(workspace, args.file, args.mode, target_content, replacement_content):
        print("Failed to apply modifications.", file=sys.stderr)
        sys.exit(1)
        
    print("Atomic operation completed successfully.")

if __name__ == "__main__":
    main()
