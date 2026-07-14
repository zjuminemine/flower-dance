#!/bin/bash

APP_NAME="朝花夕拾 Flower Dance"
BACKEND_PORT=8000
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
PYTHON_PATH="python3"

DEMO_MODE=false
DEMO_USER=""

ensure_runtime() {
    if ! command -v "$PYTHON_PATH" >/dev/null 2>&1; then
        echo "  ✗ 未找到 $PYTHON_PATH，请先安装 Python 3.9+"
        exit 1
    fi

    if ! "$PYTHON_PATH" -c "import fastapi, uvicorn, requests, docx, PyPDF2" >/dev/null 2>&1; then
        echo "  正在安装后端依赖..."
        if ! "$PYTHON_PATH" -m pip install -r "$BACKEND_DIR/requirements.txt"; then
            echo "  ✗ 依赖安装失败，请检查网络与 Python 环境"
            exit 1
        fi
    fi
}

open_application() {
    local app_url="http://127.0.0.1:$BACKEND_PORT"
    case "$(uname -s)" in
        Darwin)
            open "$app_url"
            ;;
        Linux)
            if command -v xdg-open >/dev/null 2>&1; then
                xdg-open "$app_url" >/dev/null 2>&1 || true
            else
                echo "  请在浏览器中打开: $app_url"
            fi
            ;;
        *)
            echo "  请在浏览器中打开: $app_url"
            ;;
    esac
}

usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --demo              启动后自动进入演示模式"
    echo "  --demo-user <user>  指定演示用户 (demo_user_a/demo_user_b/demo_user_c)"
    echo "  --list-demo-users   列出可用的演示用户"
    echo "  -h, --help          显示此帮助信息"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --demo)
            DEMO_MODE=true
            shift
            ;;
        --demo-user)
            DEMO_USER="$2"
            shift 2
            ;;
        --list-demo-users)
            echo "============================================="
            echo "        $APP_NAME - 可用演示用户"
            echo "============================================="
            echo ""
            
            ensure_runtime
            mkdir -p "$PROJECT_DIR/logs"
            cd "$BACKEND_DIR"
            "$PYTHON_PATH" -m uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT" > "$PROJECT_DIR/logs/backend.log" 2>&1 &
            BACKEND_PID=$!
            
            MAX_WAIT=15
            WAIT_COUNT=0
            while true; do
                if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$BACKEND_PORT/api/demo/users" | grep -q "200"; then
                    break
                fi
                WAIT_COUNT=$((WAIT_COUNT + 1))
                if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
                    echo "  ✗ 无法连接到后端服务"
                    kill $BACKEND_PID 2>/dev/null
                    exit 1
                fi
                sleep 1
            done
            
            curl -s "http://127.0.0.1:$BACKEND_PORT/api/demo/users" | python3 -m json.tool | grep -E "(id|name|description|tags|card_count)" | sed 's/^ *//'
            
            kill $BACKEND_PID 2>/dev/null
            wait $BACKEND_PID 2>/dev/null
            exit 0
            ;;
        -h|--help)
            usage
            ;;
        *)
            shift
            ;;
    esac
done

echo "============================================="
echo "        $APP_NAME"
echo "============================================="
echo ""

if $DEMO_MODE; then
    echo "[演示模式] 启动后将自动加载演示数据"
    if [ -n "$DEMO_USER" ]; then
        echo "[演示模式] 指定用户: $DEMO_USER"
    fi
    echo ""
fi

echo "[1/5] 检查 Python 与依赖..."
ensure_runtime
echo "  ✓ Python 与后端依赖已就绪"

mkdir -p "$PROJECT_DIR/logs"

echo ""
echo "[2/5] 检查端口占用..."
if command -v lsof >/dev/null 2>&1 && lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  端口 $BACKEND_PORT 被占用，正在释放..."
    lsof -Pi ":$BACKEND_PORT" -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
    sleep 2
    echo "  ✓ 端口已释放"
elif command -v lsof >/dev/null 2>&1; then
    echo "  ✓ 端口 $BACKEND_PORT 可用"
else
    echo "  未安装 lsof，启动时将由后端检查端口"
fi

echo ""
echo "[3/5] 启动后端服务..."
cd "$BACKEND_DIR"
"$PYTHON_PATH" -m uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT" > "$PROJECT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"
echo "  日志文件: $PROJECT_DIR/logs/backend.log"

echo ""
echo "[4/5] 等待后端就绪..."
MAX_WAIT=30
WAIT_COUNT=0
while true; do
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$BACKEND_PORT/api/health" | grep -q "200"; then
        echo "  ✓ 后端服务已就绪"
        break
    fi
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo "  ✗ 后端启动超时，请检查日志文件"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    sleep 1
    echo -n "."
done
echo ""

if $DEMO_MODE; then
    echo ""
    echo "[演示模式] 正在加载演示数据..."
    DEMO_URL="http://127.0.0.1:$BACKEND_PORT/api/demo/enter"
    if [ -n "$DEMO_USER" ]; then
        DEMO_URL="$DEMO_URL?user_id=$DEMO_USER"
    fi
    RESPONSE=$(curl -s -X POST "$DEMO_URL")
    if echo "$RESPONSE" | grep -q '"success": true'; then
        echo "  ✓ 已进入演示模式"
        USER_NAME=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('user',{}).get('name',''))")
        CARDS_COUNT=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cards_count',0))")
        if [ -n "$USER_NAME" ]; then
            echo "  ✓ 当前用户: $USER_NAME"
        fi
        echo "  ✓ 加载卡片: $CARDS_COUNT 张"
    else
        ERROR_MSG=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','未知错误'))")
        echo "  ✗ 进入演示模式失败: $ERROR_MSG"
    fi
fi

echo ""
echo "[5/5] 打开应用..."
open_application

echo ""
echo "============================================="
if $DEMO_MODE; then
    echo "  $APP_NAME 演示模式已启动"
else
    echo "  $APP_NAME 已启动"
fi
echo "  访问地址: http://127.0.0.1:$BACKEND_PORT"
echo "  按 Ctrl+C 退出并停止后端服务"
echo "============================================="

cleanup() {
    echo ""
    echo "正在停止后端服务..."
    kill $BACKEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    echo "服务已停止，再见！"
}

trap cleanup SIGINT SIGTERM

while true; do
    sleep 1
done
