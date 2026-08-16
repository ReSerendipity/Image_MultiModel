# 部署指南 (Deployment Guide)

本文档详细介绍 Image MultiModel 在生产环境的部署方案，涵盖单机部署、反向代理、多用户场景和备份策略。

---

## 目录

- [① 单机部署（推荐）](#①-单机部署推荐)
- [② 反向代理配置](#②-反向代理配置)
- [③ 多用户部署注意事项](#③-多用户部署注意事项)
- [④ 备份策略](#④-备份策略)
- [⑤ Docker 部署](#docker-部署)
- [⑥ ComfyUI 独立部署](#comfyui-独立部署)

---

## ① 单机部署（推荐）

适用于个人使用或小型团队，Image MultiModel 与 ComfyUI 运行在同一台机器上。

### 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 22.04+ / Debian 12+ / CentOS 8+ / Windows 10+ |
| GPU | NVIDIA CUDA GPU（推荐 8GB+ VRAM） |
| Python | 3.10+（推荐 3.12） |
| ComfyUI | 0.31.1+ |
| 磁盘 | 20GB+（模型 + 输出 + 日志） |

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/ReSerendipity/Image_MultiModel.git
cd Image_MultiModel

# 2. 安装依赖
chmod +x install.sh start.sh
./install.sh

# 3. 配置 config.yaml
#    - 设置 ComfyUI 地址（comfy.backends.local.base_url）
#    - 设置模型路径模式（models.model_source_mode: shared / portable）
#    - 设置引擎配置

# 4. 启动
./start.sh
# 或
python bin/clean_launch.py
```

### systemd 服务配置（Linux）

创建 `/etc/systemd/system/image-multimodel.service`：

```ini
[Unit]
Description=Image MultiModel - Multi-Model AI Image Generation Platform
After=network.target
Wants=comfyui.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/Image_MultiModel
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/opt/Image_MultiModel/bin
ExecStart=/usr/bin/python3 /opt/Image_MultiModel/bin/clean_launch.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# 安全限制
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/Image_MultiModel/data /opt/Image_MultiModel/outputs /opt/Image_MultiModel/logs

# 资源限制
MemoryMax=32G
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

ComfyUI 服务 `/etc/systemd/system/comfyui.service`：

```ini
[Unit]
Description=ComfyUI Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/ComfyUI
Environment=CUDA_VISIBLE_DEVICES=0
ExecStart=/usr/bin/python3 main.py --listen 127.0.0.1 --port 8188 --lowvram
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable comfyui image-multimodel
sudo systemctl start comfyui
sudo systemctl start image-multimodel

# 查看状态
sudo systemctl status image-multimodel
sudo journalctl -u image-multimodel -f
```

### 防火墙端口开放

```bash
# 仅开放必要端口（如果使用反向代理，只需开放 80/443）
# ComfyUI 内部端口（仅本机访问，不对外开放）
# Image MultiModel 内部端口（仅本机访问，不对外开放）

# 如果不使用反向代理，需要开放 8288 端口
sudo ufw allow 8288/tcp
# 但强烈建议使用反向代理 + 鉴权
```

---

## ② 反向代理配置

### Nginx 配置

**关键**：WebSocket (`/api/ws`) 和 SSE (`/api/events`) 是长连接，必须正确配置代理参数，否则会出现连接断开、超时、进度不更新等问题。

```nginx
# /etc/nginx/sites-available/image-multimodel.conf

upstream image_multimodel {
    server 127.0.0.1:8288;
    keepalive 32;
}

upstream comfyui_backend {
    server 127.0.0.1:8188;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    # 如需 HTTPS，使用 certbot 自动配置 SSL
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # ── 安全头 ──
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # ── 客户端上传限制（图像上传可能较大） ──
    client_max_body_size 2000M;
    client_body_buffer_size 256k;

    # ── 静态资源缓存 ──
    location /static/ {
        proxy_pass http://image_multimodel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # ── SSE 端点（长连接，关键配置！） ──
    location /api/events {
        proxy_pass http://image_multimodel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 关键参数
        proxy_buffering off;           # 禁用缓冲，否则事件会积压不推送
        proxy_cache off;               # 禁用缓存
        proxy_read_timeout 3600s;      # 长连接超时 1 小时
        proxy_send_timeout 3600s;
        chunked_transfer_encoding on;

        # HTTP/1.1 长连接
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # ── WebSocket 端点（长连接，关键配置！） ──
    location /api/ws {
        proxy_pass http://image_multimodel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 关键参数
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 86400s;     # WS 连接超时 24 小时
        proxy_send_timeout 86400s;
    }

    # ── 图片输出（大文件下载） ──
    location /api/outputs/ {
        proxy_pass http://image_multimodel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 大文件传输优化
        proxy_max_temp_file_size 0;
        proxy_request_buffering off;
        sendfile on;
        tcp_nopush on;
    }

    # ── API 路由 ──
    location /api/ {
        proxy_pass http://image_multimodel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 30s;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # ── 前端单页应用 ──
    location / {
        proxy_pass http://image_multimodel;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/image-multimodel.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS 配置（推荐）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 自动配置 SSL
sudo certbot --nginx -d your-domain.com

# 自动续期已内置，测试续期：
sudo certbot renew --dry-run
```

---

## ③ 多用户部署注意事项

### 并发数限制

| 参数 | 配置位置 | 推荐值 | 说明 |
|------|----------|--------|------|
| Uvicorn Workers | `config.yaml` → `server.workers` | 1 | ComfyUI 是单 GPU 串行推理，多 Worker 无益 |
| Task Queue 大小 | `config.yaml` → `runtime.task_queue.maxsize` | 100 | 队列满时返回 503 |
| Rate Limit (推理) | `config.yaml` → `security.rate_limit.infer_per_minute` | 30 | 防止单用户滥用 |
| Rate Limit (上传) | `config.yaml` → `security.rate_limit.upload_per_minute` | 10 | |
| Rate Limit (全局) | `config.yaml` → `security.rate_limit.global_per_minute` | 600 | |
| 内容过滤 fail-closed | `config.yaml` → `security.content_filter.fail_closed_on_clip_missing` | false | true=CLIP 模型缺失时拒绝生成（fail-closed），推荐生产启用 |
| ComfyUI 队列 | ComfyUI 启动参数 `--queue-size` | 10 | ComfyUI 内部队列深度 |

### 用户隔离（多租户思路）

Image MultiModel 目前是**单用户设计**。如需多租户支持，需要以下改造：

1. **鉴权层**：启用 `config.yaml` → `security.api_token.enabled: true`，为每个用户分配独立 Token
2. **数据隔离**：在 `HistoryDB` 层添加 `user_id` 字段，所有查询带用户过滤
3. **输出隔离**：`outputs/` 目录按 `user_id/engine/date/` 分层
4. **配置隔离**：每个用户独立 `config.yaml` 或 per-user override
5. **资源配额**：限制每用户的并发任务数和输出存储空间

### 鉴权配置

**Basic Auth**：
```yaml
# config.yaml
security:
  basic_auth:
    enabled: true
    username: admin
    password_bcrypt_hash: "$2b$12$..."  # 使用 python -c "import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
```

**API Token**：
```yaml
# config.yaml
security:
  api_token:
    enabled: true
    tokens:
      - "your-32-byte-secret-token-here"  # 生成: python -c "import secrets; print(secrets.token_hex(32))"
```

使用 Token 时，请求头需携带：
```
Authorization: Bearer your-32-byte-secret-token-here
```

---

## ④ 备份策略

### SQLite 数据库备份

```bash
# 在线备份（不影响运行）
sqlite3 /opt/Image_MultiModel/data/history.db ".backup /backup/history_$(date +%Y%m%d).db"

# 使用 .dump 导出 SQL（适合迁移）
sqlite3 /opt/Image_MultiModel/data/history.db ".dump" > /backup/history_$(date +%Y%m%d).sql

# 压缩备份
gzip /backup/history_$(date +%Y%m%d).db

# 自动清理 7 天前的备份
find /backup -name "history_*.db.gz" -mtime +7 -delete
```

### 输出图片备份

```bash
# rsync 增量备份
rsync -av --progress /opt/Image_MultiModel/outputs/ /backup/outputs/

# 或使用 tar 打包
tar -czf /backup/outputs_$(date +%Y%m%d).tar.gz -C /opt/Image_MultiModel outputs/

# 大量图片时使用 find + tar 分批
find /opt/Image_MultiModel/outputs -name "*.png" -newer /backup/last_backup_marker | tar -czf /backup/outputs_inc_$(date +%Y%m%d).tar.gz -T -
touch /backup/last_backup_marker
```

### 配置文件备份

```bash
# 备份 config.yaml 和关键配置
cp /opt/Image_MultiModel/config.yaml /backup/config_$(date +%Y%m%d).yaml

# 备份预设导出
curl -s http://127.0.0.1:8288/api/presets/export > /backup/presets_$(date +%Y%m%d).json
```

### 自动备份脚本

创建 `/opt/Image_MultiModel/scripts/backup.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/backup/image_multimodel"
DATE=$(date +%Y%m%d)
APP_DIR="/opt/Image_MultiModel"

mkdir -p "$BACKUP_DIR"

# 1. SQLite 备份
sqlite3 "$APP_DIR/data/history.db" ".backup $BACKUP_DIR/history_$DATE.db"
gzip "$BACKUP_DIR/history_$DATE.db"

# 2. 输出图片增量备份
rsync -a --delete "$APP_DIR/outputs/" "$BACKUP_DIR/outputs/"

# 3. 配置备份
cp "$APP_DIR/config.yaml" "$BACKUP_DIR/config_$DATE.yaml"

# 4. 清理 30 天前的备份
find "$BACKUP_DIR" -name "history_*.db.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "config_*.yaml" -mtime +30 -delete

echo "Backup completed: $DATE"
```

添加 cron 定时任务：

```bash
# 每天凌晨 2 点备份
0 2 * * * /opt/Image_MultiModel/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## Docker 部署

参见项目根目录的 `Dockerfile` 和 `docker-compose.yml`。

```bash
# 构建镜像
docker build -t image-multimodel .

# 使用 docker compose
docker compose up -d

# 查看日志
docker compose logs -f
```

**Docker 注意事项**：
- 需要安装 NVIDIA Container Toolkit 以支持 GPU
- 模型文件建议挂载 volume，不要打包到镜像中
- `config.yaml` 中的 ComfyUI 地址需根据网络拓扑调整

---

## ComfyUI 独立部署

如果 ComfyUI 运行在另一台机器上（很多人 ComfyUI 是一直开着的，Image_MultiModel 只是前端壳）：

1. **修改 `config.yaml`**：

```yaml
comfy:
  backends:
    local:
      name: local
      display_name: 远程 ComfyUI
      base_url: http://192.168.1.100:8188       # ComfyUI 机器的 IP
      ws_url: ws://192.168.1.100:8188/ws        # WebSocket 地址
      auth_token: ''                             # 如有鉴权则填写
      client_id_prefix: img_multimodel_
      health_check_interval_s: 30
      auto_spawn_if_dead: false                  # 远程模式不自动启动
```

2. **模型路径模式**：远程 ComfyUI 时使用 `shared` 模式，`comfy_models_dir` 指向远程机器的 ComfyUI models 目录（需网络共享或 NFS 挂载）

3. **网络要求**：
   - Image MultiModel → ComfyUI 的 8188 端口需可达
   - WebSocket (`ws://`) 连接需保持长连接
   - 如有防火墙，需开放 8188 端口（仅限内网）

4. **延迟注意**：WebSocket 实时预览（`b_preview`）会传输 base64 图片数据，网络延迟较高时可能影响预览流畅度

---

## 监控与日志

### 日志位置

| 日志 | 位置 | 说明 |
|------|------|------|
| 应用日志 | `logs/app.log` | RotatingFileHandler，按 `config.logging.max_size_mb` 轮转 |
| systemd 日志 | `journalctl -u image-multimodel` | stdout/stderr |
| Nginx 访问日志 | `/var/log/nginx/access.log` | |
| Nginx 错误日志 | `/var/log/nginx/error.log` | |

### 健康检查

```bash
# 基本健康检查
curl http://127.0.0.1:8288/api/health | jq .

# GPU 状态
curl http://127.0.0.1:8288/api/gpu | jq .

# 引擎状态
curl http://127.0.0.1:8288/api/engine/engines | jq .
```

### 性能监控

```bash
# GPU 利用率
nvidia-smi -l 2

# 进程资源
htop -p $(pgrep -f clean_launch)

# 磁盘使用
du -sh /opt/Image_MultiModel/outputs/ /opt/Image_MultiModel/data/ /opt/Image_MultiModel/logs/
```

---

## 故障排查

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| SSE 进度不更新 | Nginx 缓冲未关闭 | 确认 `proxy_buffering off;` |
| WebSocket 断开 | 代理超时太短 | 增加 `proxy_read_timeout` |
| 502 Bad Gateway | 后端未启动 | `systemctl status image-multimodel` |
| 503 Service Unavailable | 任务队列满 | 增大 `runtime.task_queue.maxsize` |
| 图片生成失败 | ComfyUI 不可达 | 检查 `config.yaml` 中 ComfyUI 地址 |
| OOM / CUDA Error | 显存不足 | 降低分辨率/batch_size，启用 `--lowvram` |
| 历史记录丢失 | SQLite 文件损坏 | 从备份恢复，或使用 `.dump` 修复 |
