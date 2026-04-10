# Palworld Save Analysis Tool

一个面向幻兽帕鲁服务端存档的独立分析与编辑工具项目，提供本地构建、二进制发布、存档解析、世界配置读取写入，以及部分玩家、公会数据更新能力。

## 功能概览

- 解析 `Level.sav` 与 `Players` 目录，输出统一 JSON 数据
- 读取 `WorldOption.sav` 并输出结构化配置
- 写入 `WorldOption.sav`
- 按 JSON 载荷更新玩家数据
- 按 JSON 载荷更新公会与基地数据
- 支持本地 Windows 打包
- 支持 GitHub Release 自动打包并上传发布资产

## 适用场景

- 想快速分析幻兽帕鲁服务端玩家、公会、帕鲁和物品数据
- 想将存档解析能力集成到自己的面板、工具链或自动化流程
- 想在不直接手改二进制存档的前提下，对部分数据进行程序化调整

## 项目结构

- `tools/palworld_save_analysis.py`：命令行入口，负责解析和操作分发
- `tools/palworld_save_edit.py`：玩家、公会、世界配置的写入逻辑
- `tools/palworld_save_tools/`：底层存档解析库与运行库
- `scripts/build.ps1`：本地构建脚本
- `scripts/test-smoke.ps1`：本地烟雾测试脚本
- `docs/usage.md`：补充使用文档
- `.github/workflows/release-build.yml`：Release 自动打包流程

## 环境要求

- Windows
- Python 3.11
- PowerShell 7，建议使用 `pwsh`

## 快速开始

### 1. 本地构建

在项目根目录执行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

默认输出目录：

```text
dist\win32-x64\palworld-save-analysis.exe
```

### 2. 解析存档

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --players-dir "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Players"
```

### 3. 做一次烟雾测试

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\test-smoke.ps1 `
  -ServerRoot "C:\PalServer"
```

脚本会自动：

- 查找当前服务端中的可用 `Level.sav`
- 推导对应的 `Players` 目录
- 调用二进制执行解析
- 校验输出中是否包含关键结构
- 将结果写入 `test-output/analysis.json`

## 命令行说明

主程序支持以下运行模式：

- `analyze`
- `read-world-option`
- `write-world-option`
- `update-player`
- `update-guild`

### 通用参数

- `--level`：`Level.sav` 的绝对路径，必填
- `--players-dir`：`Players` 目录绝对路径，部分模式需要
- `--operation`：运行模式，默认 `analyze`
- `--payload-file`：更新载荷 JSON 文件路径，写入操作需要
- `--world-option`：`WorldOption.sav` 路径，世界配置相关操作需要

### 分析模式

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --players-dir "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Players" `
  --operation analyze
```

输出为 JSON，主要包含：

- `meta`
- `players`
- `guilds`

### 读取世界配置

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --operation read-world-option `
  --world-option "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\WorldOption.sav"
```

### 写入世界配置

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --operation write-world-option `
  --world-option "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\WorldOption.sav" `
  --payload-file ".\payloads\world-option.json"
```

### 更新玩家

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --players-dir "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Players" `
  --operation update-player `
  --payload-file ".\payloads\player-update.json"
```

### 更新公会

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --operation update-guild `
  --payload-file ".\payloads\guild-update.json"
```

## 输出结果说明

分析模式通常会返回以下信息：

- 玩家基础信息
- 玩家容器信息
- 物品栏物品数据
- 跟随帕鲁与仓库帕鲁数据
- 公会信息
- 基地信息

程序在解析过程中可能输出部分 warning，例如地图对象未识别、结构类型回退等。若最终 JSON 正常生成，通常不影响主要分析结果。

## CI/CD 发布

项目已内置 GitHub Actions 工作流，在创建并发布 GitHub Release 时自动触发打包。

工作流行为：

- 使用 `windows-latest`
- 安装 Python 3.11
- 执行 `scripts/build.ps1`
- 压缩 `dist/win32-x64/` 目录
- 上传为当前 Release 的附件
- 同时保留一份 Actions Artifact

如果发布标签为 `v1.0.0`，产物名称类似：

```text
palworld-save-analysis-v1.0.0-win32-x64.zip
```

## 开发说明

- 构建过程中会生成 `.venv-build/`、`.build-tools/`、`dist/`、`test-output/`
- 这些目录已经加入 `.gitignore`
- 建议日常使用 `pwsh` 执行脚本，避免不同 PowerShell 版本带来的编码兼容问题

## 注意事项

- 写入类操作会直接修改存档，请先自行备份
- 尽量传入绝对路径，减少工作目录差异导致的问题
- 若服务端存档版本发生明显变化，个别字段解析可能需要跟进调整

## 补充文档

更简要的使用说明见：

- [docs/usage.md](C:\Users\17737\Code\game_tools\palworld\docs\usage.md)
