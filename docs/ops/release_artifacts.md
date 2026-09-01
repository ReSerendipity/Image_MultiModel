# 不可变版本 artifact（P1-10）

> 评估依据：`OPS_STABILITY_ASSESSMENT_v2.0.0.md` §9-P1-10
> 实现脚本：`scripts/build_release_metadata.py`
> 回归测试：`tests/release/test_build_release_metadata.py`（CI job `release-artifacts`）

## 1. 为什么

浮动 tag（`latest`）会让「线上跑的是哪份代码」无法回答：同一个 tag 可以被反复覆盖推送，
回滚时拉到的是新镜像，事故复盘也无法复现当时的二进制。P1-10 要求把发布单元变成
**一次构建、永久可寻址**的制品。

## 2. 三类不可变引用

| 层级 | 载体 | 是否可覆盖 | 落地位置 |
|---|---|---|---|
| 语义版本 / Git SHA | 镜像 tag | tag 可被重推 | `docker-compose.yml` → `image: image-multimodel:${IMAGE_TAG:?...}` |
| 镜像 digest | `sha256:...` | **不可变** | `docker-compose.release.yml` → `image: image-multimodel:${IMAGE_TAG}@${IMAGE_DIGEST}` |
| 来源元数据 | `release/build_metadata.json` | 随构建生成 | 随镜像交付至 `/app/release/`，并作为 Release 附件 |

## 3. 操作步骤

### 3.1 本地构建（开发联调）

```bash
python scripts/build_release_metadata.py            # tag = git-<sha12>，写入 .env
docker compose up -d                                # 使用 tag 固定
```

### 3.2 正式发布

```bash
# 1) 生成语义版本 tag + SBOM + 来源快照（.env 写入 IMAGE_TAG）
python scripts/build_release_metadata.py --version v2.0.1

# 2) 构建并推送（CI 的 release.yml 已自动执行）
docker build --build-arg IMAGE_TAG=2.0.1 --build-arg GIT_SHA=$(git rev-parse HEAD) \
  --build-arg BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ) -t image-multimodel:2.0.1 .
docker push image-multimodel:2.0.1

# 3) 取 digest 并回写 .env（digest 只能通过 registry/inspect 获得，无法提前推导）
DIGEST=$(docker buildx imagetools inspect image-multimodel:2.0.1 --format '{{.Manifest.Digest}}')
python scripts/build_release_metadata.py --version v2.0.1 --digest "$DIGEST"

# 4) 发布前校验（工作树必须干净、tag 不可变、快照无漂移、SBOM 存在）
python scripts/build_release_metadata.py --verify --strict

# 5) 按 digest 部署
docker compose -f docker-compose.yml -f docker-compose.release.yml up -d
```

> `IMAGE_TAG` / `IMAGE_DIGEST` 未设置时，compose 会**直接报错**并给出修复命令，
> 不会静默退化到 `latest`。这是刻意设计：宁可部署失败，也不要上线浮动 tag。

## 4. 产物说明

### 4.1 `release/build_metadata.json`

| 字段 | 内容 |
|---|---|
| `image_tag` / `image_tag_valid` | 不可变 tag 及其合法性判定结果 |
| `git.sha` / `git.short_sha` / `git.describe` / `git.dirty` | 代码来源与工作树状态 |
| `build.python_version` / `build.platform` | 构建环境 |
| `artifacts.config` | `config.yaml` 的 sha256 与体积（**不含**明文敏感值） |
| `artifacts.workflows` | `workflows/*.json` 逐个 sha256 |
| `artifacts.model` | `model/` 清单（名称+体积；≤512MB 的文件额外给 sha256） |
| `artifacts.comfy_kernel` | vendored 内核的**结构摘要**（`relpath:size` 排序哈希 + 文件数 + 总体积） |
| `requirements_lock_sha256` | 依赖锁哈希 |

> `comfy_kernel/` 有 1500+ 文件，逐个哈希耗时长且无必要；结构摘要足以证明
> 「发布时用的是哪一份上游副本」。需要精确定位时再对该目录单独做全量哈希。

### 4.2 `release/sbom.json`

CycloneDX 1.5 精简格式，组件来自 `requirements-lock.txt`（仅收录 `name==version` 锁定行，
跳过注释、`-r` 指令与非锁定约束），每条带 `pkg:pypi/<name>@<version>` 的 purl。

SBOM 与 `build_metadata.json` 会作为 GitHub Release 附件发布，供下游审计与漏洞排查。

## 5. CI 门禁

`ci.yml` 的 `release-artifacts` job 会在每次 push/PR 上执行：

1. 生成元数据（CI 用 `0.0.0-ci` 占位版本，跳过模型哈希以控制时长）；
2. `build_release_metadata.py --verify` —— tag 必须不可变、快照无漂移、SBOM 必须存在；
3. 断言 compose 中不含 `:latest`，且两个 compose 文件分别强制要求 `IMAGE_TAG` / `IMAGE_DIGEST`；
4. 运行 `tests/release` 单元测试。

`release.yml` 在打 tag 时会执行 `--verify --strict`（额外要求工作树干净），
并把 SBOM 与来源元数据挂到 Release 上。

## 6. 已知限制

- 本仓库 CI 不推送镜像（无 registry 凭据配置），因此 digest 只能在有 registry 的环境中回填；
  `release.yml` 目前用 `docker inspect` 取本地镜像 ID 作为占位，并在注释中指明生产应改用
  `docker buildx imagetools inspect`。
- `model/` 权重通常很大，`--no-model-hash` 可跳过哈希；但**正式发布建议保留哈希**，
  以便验证模型未被静默替换。
- `.env` 由脚本合并写入（保留其他变量，仅覆盖 `IMAGE_TAG` / `IMAGE_DIGEST`），且已在
  `.gitignore` 中；`release/*.json` 同样不入库，避免生成物污染工作树。
