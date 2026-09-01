FROM python:3.12-slim

# ── P1-10 不可变版本 artifact：构建期来源元数据（由 CI 注入）──────────────
ARG IMAGE_TAG=unknown
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown

LABEL org.opencontainers.image.title="Image MultiModel" \
      org.opencontainers.image.description="Z-Image Turbo 图像生成平台（单一原生引擎）" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${IMAGE_TAG}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_TIME}" \
      org.opencontainers.image.source="https://github.com/zhengruichen/Image_MultiModel"

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
# 许可注记：comfy_kernel/（ComfyUI，GPL-3.0）已在 .dockerignore 中排除，不进入镜像；
# 运行时由 docker-compose.yml 将本地 comfy_kernel/ 只读挂载到 /app/comfy_kernel。
COPY . .

# 编译检查
RUN python -m compileall -q app tests

# 发布元数据（SBOM / 配置·模型·comfy_kernel 快照）随镜像一起交付，
# 使运行中的容器自带可追溯来源：/app/release/build_metadata.json
# release/ 内有 .gitkeep 常驻，未生成元数据时 COPY 也不会失败（内容为空目录）。
COPY release/ /app/release/

# 暴露端口
EXPOSE 8288

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8288/api/health')" || exit 1

# 启动
CMD ["python", "app/clean_launch.py"]
