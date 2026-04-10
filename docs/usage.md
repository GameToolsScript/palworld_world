# 幻兽帕鲁存档解析工具

## 项目说明

这是一个可独立构建和运行的幻兽帕鲁存档解析与编辑工具项目。

当前保留的能力包括：

- 解析 `Level.sav` 和 `Players` 目录，输出统一 JSON
- 读取与写入 `WorldOption.sav`
- 按载荷更新玩家和公会数据
- 支持在创建 GitHub Release 时自动打包 Windows / Linux 二进制
- 支持手动触发工作流并选择构建平台

## 目录结构

- `tools/palworld_save_analysis.py`：命令行入口
- `tools/palworld_save_edit.py`：存档修改逻辑
- `tools/palworld_save_tools/`：原始解析库与运行库
- `scripts/build.ps1`：本地构建脚本
- `scripts/build.sh`：Linux 本地构建脚本
- `scripts/test-smoke.ps1`：烟雾测试脚本
- `.github/workflows/release-build.yml`：Release 自动打包流程

## 构建方式

在项目根目录执行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

默认输出目录：

```text
dist\win32-x64\palworld-save-analysis.exe
```

Linux 构建示例：

```bash
EXTRA_PIP_PACKAGES="git+https://github.com/MRHRTZ/pyooz.git" ./scripts/build.sh
```

## CI/CD 打包

项目已经提供 GitHub Actions 工作流：

- 当 GitHub Release 被发布时自动触发
- 也支持在 Actions 页面手动触发
- 手动触发时可选择 `windows`、`linux` 或 `both`
- Release 触发时默认构建 Windows 和 Linux
- Windows 生成 `dist/win32-x64/` 目录内容
- Linux 生成 `dist/linux-x86_64/` 目录内容
- Windows 自动压缩为 `palworld-save-analysis-标签名-win32-x64.zip`
- Linux 自动压缩为 `palworld-save-analysis-标签名-linux-x86_64.tar.gz`
- 自动上传到当前 Release 资产

如果你发布的标签是 `v1.0.0`，最终上传的文件名类似：

```text
palworld-save-analysis-v1.0.0-win32-x64.zip
palworld-save-analysis-v1.0.0-linux-x86_64.tar.gz
```

## 解析示例

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --players-dir "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Players"
```

## 烟雾测试

对实际服务端执行一次解析测试：

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\test-smoke.ps1 `
  -ServerRoot "C:\PalServer"
```

脚本会自动：

- 查找一个可用的 `Level.sav`
- 推导对应 `Players` 目录
- 执行二进制解析
- 校验输出 JSON 结构
- 将结果写入 `test-output/analysis.json`

## 进阶用法

读取世界配置：

```powershell
.\dist\win32-x64\palworld-save-analysis.exe `
  --level "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\Level.sav" `
  --operation read-world-option `
  --world-option "C:\PalServer\Pal\Saved\SaveGames\0\WorldId\WorldOption.sav"
```

更新操作需要额外传入 `--payload-file`，载荷格式可参考上游项目的面板调用数据。
