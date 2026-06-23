import os

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = os.path.dirname(SPECPATH)


def project_path(*parts):
    return os.path.join(project_root, *parts)


datas = [
    (project_path("static"), "static"),
    (project_path("mcp_server", "learnflow-mcp-server", "build"), "mcp_server/learnflow-mcp-server/build"),
    (project_path("mcp_server", "learnflow-mcp-server", "node_modules"), "mcp_server/learnflow-mcp-server/node_modules"),
    (project_path("mcp_server", "learnflow-mcp-server", "package.json"), "mcp_server/learnflow-mcp-server"),
    (project_path("packaging", "node"), "node"),
    (project_path("packaging", "使用说明.txt"), "."),
]
binaries = []
hiddenimports = []

for package in ("gradio", "litellm", "llama_index", "sentence_transformers", "transformers"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

hiddenimports += ["mcp_tool_runner"]
hiddenimports += collect_submodules("llama_index")

a = Analysis(
    [project_path("app.py")],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LearnFlow-AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LearnFlow-AI",
)
