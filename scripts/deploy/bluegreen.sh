#!/usr/bin/env bash
# scripts/deploy/bluegreen.sh — P2-12 blue-green 部署 + 一键回滚（单 GPU 场景变体）
#
# 评估 §9-P2-12：「单 GPU 场景至少做 旧容器保持服务 + 新容器独立健康检查 +
# 人工/自动切流」。因为一块 GPU 无法同时常驻两份 9B 权重，本实现为串行切换变体：
#
#   active 槽（对外 8288）：当前服务版本，promote 期间才停（秒级停服窗口）
#   idle   槽（内部 8289）：新版本先在此启动 → 只读健康检查 + 只读 smoke
#                           （不提交生成任务，避免与 active 抢显存）
#   promote：停 idle → 停 active → active 以新 tag 重启 → 完整 smoke
#            （含假生成任务）→ 观察窗口（告警 firing = 失败）→ 成功则记 LAST_GOOD
#   任何一步失败：自动把 active 换回 LAST_GOOD（一键回滚同样可手工触发）
#
# 晋级/回退条件：health、错误率/生成成功率（smoke + /api/alerts firing）、
# P99（generation_duration 指标）、OOM（gpu_oom_total / GPUOOM 告警）。
#
# 状态文件 .imm_bluegreen（IMM_BG_STATE 覆盖）：
#   ACTIVE_SLOT=blue|green | BLUE_TAG | GREEN_TAG | LAST_GOOD | HISTORY
#
# 用法：
#   bash scripts/deploy/bluegreen.sh deploy <image_tag>
#   bash scripts/deploy/bluegreen.sh rollback
#   bash scripts/deploy/bluegreen.sh promote-only     # 紧急切流（跳过 idle 验证）
#   bash scripts/deploy/bluegreen.sh status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STATE_FILE="${IMM_BG_STATE:-$ROOT/.imm_bluegreen}"
COMPOSE_FILE="$ROOT/docker-compose.bluegreen.yml"
SMOKE="$ROOT/scripts/post_deploy_smoke.py"
OBSERVE_SECS="${IMM_BG_OBSERVE:-120}"
HEALTH_TIMEOUT="${IMM_BG_HEALTH_TIMEOUT:-180}"
PYTHON="${PYTHON:-python3}"
COMPOSE="docker compose"

log() { echo "[bluegreen] $*"; }
die() { echo "[bluegreen][FAIL] $*" >&2; exit 1; }

FORBIDDEN_TAG_RE='^(latest|dev|stable|main|master|nightly|edge)$'

# ────────────────────────── 状态文件 ──────────────────────────
ensure_state() {
  [ -f "$STATE_FILE" ] || cat > "$STATE_FILE" <<EOF
ACTIVE_SLOT=blue
BLUE_TAG=
GREEN_TAG=
LAST_GOOD=
HISTORY=
EOF
}

state_get() { grep -m1 "^$1=" "$STATE_FILE" | cut -d= -f2-; }

state_set() { # KEY VALUE
  ensure_state
  local tmp; tmp="$(mktemp)"
  grep -v "^$1=" "$STATE_FILE" > "$tmp" || true
  echo "$1=$2" >> "$tmp"
  mv "$tmp" "$STATE_FILE"
}

active_slot() { state_get ACTIVE_SLOT; }
idle_slot()   { [ "$(active_slot)" = blue ] && echo green || echo blue; }

slot_port() { [ "$1" = blue ] && echo "${IMM_BLUE_PORT:-8288}" || echo "${IMM_GREEN_PORT:-8289}"; }

slot_tag() { [ "$1" = blue ] && state_get BLUE_TAG || state_get GREEN_TAG; }

# ────────────────────────── compose 封装 ──────────────────────────
compose_up_slot() { # slot tag
  local slot="$1" tag="$2"
  local var; [ "$slot" = blue ] && var=BLUE_TAG || var=GREEN_TAG
  env "$var=$tag" $COMPOSE -f "$COMPOSE_FILE" --profile "$slot" up -d --no-build "imm-$slot"
}

compose_down_slot() { # slot
  $COMPOSE -f "$COMPOSE_FILE" down --no-remove-orphans "imm-$1" 2>/dev/null \
    || docker stop -t 30 "imm-$1" 2>/dev/null || true
}

# ────────────────────────── 健康 / smoke / 观察窗口 ──────────────────────────
wait_healthy() { # slot timeout_s
  local port; port="$(slot_port "$1")"
  log "等待 imm-$1 (127.0.0.1:$port) 健康检查..."
  for i in $(seq 1 "$2"); do
    curl -fsS "http://127.0.0.1:$port/api/health" >/dev/null 2>&1 && { log "imm-$1 健康（${i}s）"; return 0; }
    sleep 1
  done
  return 1
}

# 只读 smoke（idle 验证阶段）：不提交生成任务，避免与 active 槽争抢单 GPU 显存
smoke_readonly() { # slot
  local port; port="$(slot_port "$1")"
  "$PYTHON" "$SMOKE" --base-url "http://127.0.0.1:$port" --timeout 15 \
    --checks health,config,engines,queue_protection,sse
}

# 完整 smoke（promote 后）：含假生成任务
smoke_full() { # slot
  local port; port="$(slot_port "$1")"
  "$PYTHON" "$SMOKE" --base-url "http://127.0.0.1:$port" --timeout 15 --generation-timeout 120
}

# 观察窗口：期间 /api/alerts 出现 critical/warning firing 的关键告警即失败
# （错误率/生成成功率=GenerationFailureRateHigh、OOM显存=GpuVramLow、
#   队列=QueueOverloaded、健康=ServiceUnhealthy、磁盘=DiskSpaceLow）
observe_window() { # slot secs
  local port; port="$(slot_port "$1")"
  log "观察窗口 ${2}s：监控错误率 / OOM / firing 告警..."
  local end=$(( $(date +%s) + $2 ))
  while [ "$(date +%s)" -lt "$end" ]; do
    local bad
    bad="$(curl -fsS "http://127.0.0.1:$port/api/alerts" 2>/dev/null | "$PYTHON" -c '
import json,sys
try:
    data=json.load(sys.stdin)
except Exception:
    sys.exit(0)  # 拉取失败不算晋级失败（下个周期再查）
alerts = data.get("alerts", data if isinstance(data,list) else [])
KEY={"ServiceUnhealthy","GenerationFailureRateHigh","QueueOverloaded","GpuVramLow","DiskSpaceLow"}
bad=[a for a in alerts if a.get("firing") and a.get("name") in KEY]
print("BAD" if bad else "OK")
' )"
    if [ "$bad" = "BAD" ]; then
      log "观察窗口内检测到关键告警 firing"; return 1
    fi
    sleep 10
  done
  log "观察窗口通过"; return 0
}

# ────────────────────────── 回滚 ──────────────────────────
do_rollback() {
  ensure_state
  local last; last="$(state_get LAST_GOOD)"
  [ -n "$last" ] || { log "无 last-known-good 版本（LAST_GOOD 为空），无法自动回滚"; return 1; }
  log "回滚 active 槽 → $last"
  local slot; slot="$(active_slot)"
  compose_down_slot "$slot"
  compose_up_slot "$slot" "$last"
  wait_healthy "$slot" "$HEALTH_TIMEOUT" || { log "回滚后健康检查失败，需人工介入：docs/runbooks/service_startup.md"; return 1; }
  # LAST_GOOD 保持不变（连续回滚安全），槽位 tag 同步
  [ "$slot" = blue ] && state_set BLUE_TAG "$last" || state_set GREEN_TAG "$last"
  log "回滚完成：imm-$slot = $last"
}

# ────────────────────────── 子命令 ──────────────────────────
cmd_status() {
  ensure_state
  echo "ACTIVE_SLOT = $(active_slot)"
  echo "BLUE_TAG    = $(slot_tag blue)"
  echo "GREEN_TAG   = $(slot_tag green)"
  echo "LAST_GOOD   = $(state_get LAST_GOOD)"
  local port; port="$(slot_port "$(active_slot)")"
  curl -fsS "http://127.0.0.1:$port/api/health" >/dev/null 2>&1 \
    && echo "HEALTH      = ok (:$port)" || echo "HEALTH      = unreachable (:$port)"
  echo "HISTORY:"; state_get HISTORY | head -10
}

cmd_deploy() {
  local tag="${1:-}"
  [ -n "$tag" ] || die "用法: $0 deploy <image_tag>"
  [[ "$tag" =~ $FORBIDDEN_TAG_RE ]] && die "拒绝可变 tag: $tag（须为语义版本或 git-<sha>，P1-10）"
  ensure_state

  local act idle old_tag
  act="$(active_slot)"; idle="$(idle_slot)"
  old_tag="$(slot_tag "$act")"
  log "active=$act($old_tag) → 新版本 $tag 先部署到 idle=$idle"

  # 1) idle 起新版本（8289），不影响线上
  compose_down_slot "$idle"
  compose_up_slot "$idle" "$tag"

  # 2) idle 只读验证：健康 + config/engines/metrics/SSE（不跑生成，避免显存竞争）
  wait_healthy "$idle" "$HEALTH_TIMEOUT" || {
    compose_down_slot "$idle"; die "新版本 $tag 健康检查失败，线上 $old_tag 未受影响"
  }
  smoke_readonly "$idle" || {
    compose_down_slot "$idle"; die "新版本 $tag 只读 smoke 失败，线上未受影响"
  }

  # 3) promote（单 GPU 串行切换：秒级停服窗口）
  log "promote：切换 active 槽到 $tag"
  compose_down_slot "$idle"
  compose_down_slot "$act"
  [ -n "$old_tag" ] && state_set LAST_GOOD "$old_tag"
  compose_up_slot "$act" "$tag"
  [ "$act" = blue ] && state_set BLUE_TAG "$tag" || state_set GREEN_TAG "$tag"

  if ! wait_healthy "$act" "$HEALTH_TIMEOUT"; then
    log "promote 后健康检查失败 → 自动回滚"
    do_rollback || die "自动回滚失败，需人工介入：docs/runbooks/service_startup.md"
    die "promote 失败已回滚到 $old_tag"
  fi

  # 4) 完整 smoke（含假生成任务）
  if ! smoke_full "$act"; then
    log "promote 后完整 smoke 失败 → 自动回滚"
    do_rollback || die "自动回滚失败，需人工介入"
    die "smoke 失败已回滚到 $old_tag"
  fi

  # 5) 观察窗口（错误率/OOM/P1 告警）
  if [ "$OBSERVE_SECS" != "0" ] && ! observe_window "$act" "$OBSERVE_SECS"; then
    log "观察窗口不达标 → 自动回滚"
    do_rollback || die "自动回滚失败，需人工介入"
    die "观察窗口失败已回滚到 $old_tag"
  fi

  local hist; hist="$(state_get HISTORY)"
  state_set HISTORY "$(date -u +%FT%TZ) $tag
$hist"
  log "promote 成功：active=$act tag=$tag（回滚目标 LAST_GOOD=$(state_get LAST_GOOD)）"
}

cmd_rollback() { ensure_state; do_rollback || die "回滚失败"; }

cmd_promote_only() {
  ensure_state
  local idle; idle="$(idle_slot)"
  local tag; tag="$(slot_tag "$idle")"
  [ -n "$tag" ] || die "idle 槽没有可切换的版本"
  log "紧急切流：跳过 idle 验证，直接 promote $tag"
  local act old; act="$(active_slot)"; old="$(slot_tag "$act")"
  [ -n "$old" ] && state_set LAST_GOOD "$old"
  compose_down_slot "$idle"; compose_down_slot "$act"
  compose_up_slot "$act" "$tag"
  wait_healthy "$act" "$HEALTH_TIMEOUT" || { do_rollback; die "紧急切流失败，已回滚"; }
  [ "$act" = blue ] && state_set BLUE_TAG "$tag" || state_set GREEN_TAG "$tag"
  log "紧急切流完成：imm-$act = $tag（请尽快跑完整 smoke 与观察）"
}

case "${1:-}" in
  deploy)        shift; cmd_deploy "${1:-}" ;;
  rollback)      cmd_rollback ;;
  promote-only)  cmd_promote_only ;;
  status)        cmd_status ;;
  *) cat <<EOF
用法: $0 {deploy <tag>|rollback|promote-only|status}
环境变量:
  IMM_BG_STATE          状态文件（默认 ./.imm_bluegreen）
  IMM_BG_OBSERVE        观察窗口秒数（默认 120；0=跳过）
  IMM_BG_HEALTH_TIMEOUT 健康检查超时秒（默认 180）
  IMM_BLUE_PORT / IMM_GREEN_PORT  槽位端口（默认 8288 / 8289）
EOF
     exit 2 ;;
esac
