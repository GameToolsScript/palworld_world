#!/usr/bin/env python3

import argparse
import importlib.util
import os
import platform
import shutil
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


def iter_add_data_args(source_root: Path, destination_root: str, separator: str) -> list[str]:
    args: list[str] = []
    for item in source_root.rglob("*"):
        if item.is_dir():
            continue
        if item.suffix in {".pyc", ".pyo"}:
            continue
        if "__pycache__" in item.parts:
            continue
        if item.suffix in {".pyd", ".so", ".dll", ".dylib"}:
            continue
        relative_path = item.relative_to(source_root)
        destination_path = Path(destination_root) / relative_path.parent
        args.extend(["--add-data", f"{item}{separator}{destination_path.as_posix()}"])
    return args


def iter_add_binary_args(source_root: Path, destination_root: str, separator: str) -> list[str]:
    args: list[str] = []
    for item in source_root.rglob("*"):
        if item.is_dir():
            continue
        if item.suffix not in {".pyd", ".so", ".dll", ".dylib"}:
            continue
        relative_path = item.relative_to(source_root)
        destination_path = Path(destination_root) / relative_path.parent
        args.extend(["--add-binary", f"{item}{separator}{destination_path.as_posix()}"])
    return args


def copy_runtime_libs(vendor_dir: Path, output_dir: Path) -> None:
    source_lib_dir = vendor_dir / "palworld_save_tools" / "lib"
    if not source_lib_dir.exists():
        return

    destination_lib_dir = output_dir / "lib"
    if destination_lib_dir.exists():
        shutil.rmtree(destination_lib_dir, ignore_errors=True)

    shutil.copytree(source_lib_dir, destination_lib_dir)

    windows_ooz = source_lib_dir / "windows" / "ooz.pyd"
    if windows_ooz.exists():
        shutil.copy2(windows_ooz, output_dir / "ooz.pyd")


def resolve_platform_lib_dir_name() -> str | None:
    if os.name == "nt":
        return "windows"

    if sys_platform_startswith("linux"):
        machine = platform.machine().lower()
        if "aarch64" in machine or "arm64" in machine:
            return "linux_arm64"
        if "x86_64" in machine or "amd64" in machine:
            return "linux_x86_64"
        raise RuntimeError(f"不支持的 Linux 架构: {machine}")

    if sys_platform_startswith("darwin"):
        machine = platform.machine().lower()
        if "arm64" in machine:
            return "mac_arm64"
        if "x86_64" in machine or "amd64" in machine:
            return "mac_x86_64"
        raise RuntimeError(f"不支持的 macOS 架构: {machine}")

    return None


def sys_platform_startswith(name: str) -> bool:
    return os.sys.platform.startswith(name)


def has_importable_ooz() -> bool:
    return importlib.util.find_spec("ooz") is not None


def ensure_required_runtime_files(vendor_dir: Path) -> list[str]:
    platform_lib_dir = resolve_platform_lib_dir_name()
    hidden_imports: list[str] = []

    if has_importable_ooz():
        hidden_imports.append("ooz")

    if not platform_lib_dir:
        return hidden_imports

    bundled_lib_dir = vendor_dir / "palworld_save_tools" / "lib" / platform_lib_dir
    bundled_runtime_exists = bundled_lib_dir.exists() and any(
        item.suffix in {".pyd", ".so", ".dll", ".dylib"} for item in bundled_lib_dir.rglob("*")
    )

    if bundled_runtime_exists:
        return hidden_imports

    if hidden_imports:
        return hidden_imports

    raise FileNotFoundError(
        "缺少当前平台可用的 Ooz 运行库。"
        f"已检查目录: {bundled_lib_dir}。"
        "你可以补充对应平台的运行库文件，或先安装可导入的 ooz 扩展后再执行打包。"
    )


def build_parser(output_dir: Path, binary_name: str, clean: bool) -> Path:
    tools_dir = Path(__file__).resolve().parent
    project_dir = tools_dir.parent
    vendor_dir = tools_dir / "palworld_save_tools"
    entry_script = tools_dir / "palworld_save_analysis.py"
    build_root = project_dir / ".build-tools" / "palworld-parser" / "build"
    spec_root = project_dir / ".build-tools" / "palworld-parser" / "spec"

    hidden_imports = ensure_required_runtime_files(vendor_dir)

    if clean and output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
    if clean and build_root.exists():
        shutil.rmtree(build_root, ignore_errors=True)
    if clean and spec_root.exists():
        shutil.rmtree(spec_root, ignore_errors=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)
    spec_root.mkdir(parents=True, exist_ok=True)

    data_separator = ";" if os.name == "nt" else ":"
    add_data_args = iter_add_data_args(vendor_dir, "palworld_save_tools", data_separator)
    add_binary_args = iter_add_binary_args(vendor_dir, "palworld_save_tools", data_separator)

    pyinstaller_run(
        [
            "--noconfirm",
            "--onefile",
            "--clean",
            "--console",
            "--name",
            binary_name,
            "--distpath",
            str(output_dir),
            "--workpath",
            str(build_root),
            "--specpath",
            str(spec_root),
            "--paths",
            str(vendor_dir),
            *[arg for hidden_import in hidden_imports for arg in ("--hidden-import", hidden_import)],
            *add_data_args,
            *add_binary_args,
            str(entry_script),
        ]
    )

    suffix = ".exe" if os.name == "nt" else ""
    binary_path = output_dir / f"{binary_name}{suffix}"
    if not binary_path.exists():
        raise FileNotFoundError(f"未生成解析器二进制文件: {binary_path}")

    copy_runtime_libs(vendor_dir, output_dir)
    return binary_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Palworld save parser binary")
    parser.add_argument("--output-dir", required=True, help="Binary output directory")
    parser.add_argument("--binary-name", default="palworld-save-analysis", help="Binary file name")
    parser.add_argument("--clean", action="store_true", help="Clean previous build outputs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    binary_path = build_parser(output_dir, args.binary_name, args.clean)
    print(binary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
