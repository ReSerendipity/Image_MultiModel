# SOPS — 密钥与签名操作手册（2026-09-10 桌面分发与安全加固）

> 配套：`docs/桌面分发分层定案-20260910.md`、《执行对照表》。所有私钥不入库、离线备份。

## 1. 完整性清单签名（Ed25519）

**角色与文件**
| 对象 | 路径 | 处理 |
|---|---|---|
| 清单私钥 | `data/.manifest_signing_key`（119B） | gitignored；离线备份 `C:\Users\Doro\backups\imm-signing-key-backup-20260910\` |
| GitHub Secret | `MANIFEST_SIGNING_KEY_B64`（base64 私钥） | 已设 2026-09-10T06:46:12Z，供 CI 签名 |
| 仓库公钥 | `app/integrated_app/security/manifest_signing_public_key.pem` | 入库（LF） |

**代码变更后重签（核心步骤）**
```powershell
.venv\Scripts\python.exe scripts\generate_integrity_manifest.py   # 重算 33 模块哈希（LF 写入）
.venv\Scripts\python.exe scripts\sign_integrity_manifest.py       # Ed25519 签名 + 内置公钥回验 + 公钥一致性闸门
.venv\Scripts\python.exe scripts\check_integrity_manifest.py       # 清单与检出代码一致性门禁（33/33）
```
验签失败自动回退 HMAC；发布门禁 gate-4 已固化三步。

## 2. 水印密钥
- `data/.imm_secret`：本机水印 HMAC 密钥（gitignored），权限自愈 0600/icacls；由 `app/integrated_app/security/secret_key.py::get_secret_key()` 管理。
- 恢复：删除后下次启动自动重建（无恢复负担）。

## 3. Tauri 更新签名（桌面壳增量更新）

**角色与文件**
| 对象 | 路径 | 处理 |
|---|---|---|
| 更新私钥 | `desktop/src-tauri/tauri.key` | gitignored；离线备份 `C:\Users\Doro\backups\imm-tauri-signing-key-20260910\` |
| 私钥密码 | `C:\Users\Doro\backups\imm-tauri-signer-password-20260910.txt` | 离线备份 |
| 公钥 | `desktop/src-tauri/tauri.key.pub` | 入库；内容写入 `tauri.conf.json` `plugins.updater.pubkey` |

**发版签名（CI release 流程）**
```yaml
env:
  TAURI_SIGNING_PRIVATE_KEY: <base64(tauri.key) 或 GitHub Secret>
  TAURI_SIGNING_PRIVATE_KEY_PASSWORD: <密码>
# tauri build 自动对更新包签名
```

**离线重新生成（勿复用他人密钥）**
```powershell
cd desktop
npx tauri signer generate -w src-tauri/tauri.key -f -p "<强密码>"
# 更新 tauri.conf.json pubkey = tauri.key.pub 内容
```

## 4. 发布操作序（五步门禁）
```powershell
.venv\Scripts\python.exe scripts\release_gate.py            # 构建→静态→测试→签名→发布物
.venv\Scripts\python.exe scripts\package_app.py             # 增量包 app-v{ver}.zip + sha256
.venv\Scripts\python.exe scripts\split_release_volumes.py --input ImageMultiModel-Data.7z   # 分卷 + SHA256SUMS
makensis /DVERSION=<ver> desktop\installer\setup.nsi        # 安装器（需壳 exe 与 version.json 就位）
```

## 5. 安全须知
- 私钥绝不进 git；备份目录权限收敛为当前用户。
- GitHub Secret 仅在 CI 注入；本地开发验签用仓库公钥即可。
- 密钥轮换：重生成后同步更新仓库公钥、CI Secret、离线备份三处，并发布公告。
