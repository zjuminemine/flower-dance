#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
START_SCRIPT="$SCRIPT_DIR/start.sh"

if [ ! -f "$START_SCRIPT" ]; then
    echo "错误: 找不到启动脚本 $START_SCRIPT"
    read -p "按 Enter 键退出..."
    exit 1
fi

cd "$PROJECT_DIR"
bash "$START_SCRIPT" "$@"