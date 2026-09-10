# GOTCHAS — 桌面分发与安全加固坑记录（2026-09-10）

> 与《落地执行总结》配套的实操避坑清单；按「现象 → 根因 → 解法」记录。

## 1. Windows 下 tools 安装无管理员权限
- 现象：choco install 7zip/nsis 抛 UnauthorizedAccessException；7-Zip 安装器静默安装需 elevation。
- 根因：会话无管理员令牌，MSI/EXE 安装器无法写入 Program Files。
- 解法：下载便携版——7-Zip 用 `7zr.exe`+extra 包（`C:\Users\Doro\tools\7z-extra\x64\7za.exe` v25.01）；NSIS 从 GitHub 镜像 `xmake-mirror/nsis` releases 下载 v3.09（sourceforge 403 反爬）。后续以路径直调，不进 PATH。

## 2. curl.exe schannel 证书吊销检查失败
- 现象：`curl.exe -L` 下载报 `CRYPT_E_NO_REVOCATION_CHECK`。
- 根因：Windows schannel 默认做吊销检查，代理/镜像证书链不满足。
- 解法：`curl --ssl-no-revoke` 或改用 Python urllib 下载。

## 3. NSIS 中文脚本必须 UTF-8 with BOM
- 现象：makensis 报 "Bad text encoding"。
- 根因：NSIS 3.x 对无 BOM 的 UTF-8 中文字符串解析失败。
- 解法：setup.nsi 以 UTF-8 BOM 保存；VIAddVersionKey 不要重复同 key（会 line 报错）。

## 4. Edit 工具对部分含 CJK/特殊字符文件失败（Native execution failed）
- 现象：Edit 对含 `├─`、`「」`、`运行中` 等内容的 old_string 匹配报 Native execution failed；Write 正常。
- 根因：工具环境的字符串规范化差异（与本项目代码无关）。
- 解法：改用 Write 整文件重写或 PowerShell `[System.IO.File]::ReadAllText/WriteAllText` 字节级替换（UTF-8 无 BOM 编码需显式 `New-Object System.Text.UTF8Encoding($false)`）。

## 5. GitHub 公钥行尾差异导致 SHA256 误报
- 现象：P0 公钥一致性闸门在本地 CRLF / CI LF 下验签失配。
- 根因：PEM 公钥被 .gitattributes 行尾转换改写（内容一致但字节不同）。
- 解法：用 DER 解析后比对（绕开行尾）；`.gitattributes` 强制 `*.pem text eol=lf`。

## 6. 清单重生成必须同步签名（哈希随代码变更过期）
- 现象：P1 改 app_server.py（--host/--port）后 diag 显示 7 个模块哈希失败。
- 根因：integrity_manifest.json 是 P0 生成的，代码变更后未重生成。
- 解法：任何核心模块变更后运行 `generate_integrity_manifest.py` + `sign_integrity_manifest.py`（发布门禁 gate-4 已固化）。

## 7. generate_integrity_manifest 文本模式写 CRLF
- 现象：本地生成清单与 CI(LF) 验签失配。
- 根因：open() 默认文本模式在 Windows 写 CRLF。
- 解法：写入时 `newline="\n"` 强制 LF（P0 已改）。

## 8. 桌面壳启动命令：本项目无 start_portable.py
- 现象：SeedVR2 壳调用 `python start_portable.py --port`，本项目无此文件。
- 根因：项目入口不同（`python -m integrated_app.app_server`，已加 --host/--port）。
- 解法：python_process.rs 适配为 `-m integrated_app.app_server --host 127.0.0.1 --port <port>`；app_dir 判定从 start_portable.py 改为 `integrated_app/` 目录存在；开发布局（<root>/app/integrated_app）与打包布局（app 根含 integrated_app）差异已统一处理。

## 9. 双 Python 环境并发跑 pytest 互相干扰
- 现象：一次门禁测试跑出真实采样（20 步、169s/步）近 1 小时。
- 根因：.venv 与系统 C:\Python312 两个 pytest 实例并发跑同一 tests；系统环境无 pytest-timeout 保护触发慢路径。
- 解法：门禁统一用 .venv python；清理非任务实例；单环境重跑 pytest 1018 passed+14 skipped（111s，与 P0 基线一致）。

## 10. config.yaml 被测试污染
- 现象：db_path/cache_dir 被测试 teardown 改写为 `%TEMP%\imm-hist-<pid>-xxx`。
- 根因：HistoryDB 相关测试用临时目录并在结束时写回 config。
- 解法：收尾前 `git checkout -- config.yaml`（HEAD 含 P0 安全配置两处新增：enforce: true / failure_mode: sidecar）；已记录为长期待修复项。

## 11. Cargo.lock / package-lock.json 需随包名同步
- 现象：tauri.conf.json/Cargo.toml 改名后 lock 文件仍引用旧包名。
- 根因：lock 文件记录包名。
- 解法：一并替换 `seedvr2-desktop` → `imgmulti-desktop`。

## 12. Python 命名空间包（app/ 无 __init__.py）
- 现象：`from app.integrated_app...` 可导入但 `app/__init__.py` 不存在。
- 根因：Python 3 命名空间包机制。
- 解法：diag 脚本按 `app.integrated_app` 导入；壳 resolve 以 `integrated_app/` 目录存在为判定（不依赖 __init__.py）。
