import os
import sys
import traceback
from pathlib import Path


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _log_path() -> Path:
    return _runtime_dir() / "LearnFlow-AI启动日志.txt"


def _pause_on_windows() -> None:
    if os.name == "nt" and sys.stdin is not None:
        try:
            input("\n程序启动失败，错误已写入 LearnFlow-AI启动日志.txt。按回车键关闭窗口...")
        except EOFError:
            pass


def main() -> int:
    # MCP child-process calls must keep stdout clean because the Node MCP server
    # reads the tool result from stdout.
    if len(sys.argv) >= 2 and sys.argv[1] == "--mcp-tool":
        from app import main as app_main

        app_main()
        return 0

    log_file = _log_path()
    try:
        with log_file.open("a", encoding="utf-8") as fp:
            fp.write("\n========== LearnFlow-AI 启动 ==========\n")
            fp.write(f"Executable: {sys.executable}\n")
            fp.write(f"Working directory: {os.getcwd()}\n")
            fp.write(f"Arguments: {sys.argv}\n")

        from app import main as app_main

        app_main()
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            with log_file.open("a", encoding="utf-8") as fp:
                fp.write("\n启动失败：\n")
                fp.write(error)
        finally:
            print(error)
            _pause_on_windows()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
