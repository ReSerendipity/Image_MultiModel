FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 编译检查
RUN python -m compileall -q app tests

# 非 root 运行（对齐家族实践：SeedVR2/TTS 的 appuser；云原生评估反模式 #2）
# pip 依赖装在系统 site-packages（root 阶段完成），运行期仅 /app 内读写
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8288

# 健康检查
# start-period=60s：9B 权重加载常超 60s，避免就绪前被判 unhealthy
# （与 docker-compose.yml / bluegreen 的 start_period: 60s 对齐）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8288/api/health')" || exit 1

# 启动
CMD ["python", "app/clean_launch.py"]
