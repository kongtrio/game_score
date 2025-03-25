#!/bin/bash

# 停止SSH隧道管理应用
echo "正在停止比分统计应用..."

# 查找并杀死app.py进程
pids=$(ps aux | grep 'game_score_app.py' | awk '{print $2}')
if [ -z "$pids" ]; then
    echo "没有找到运行的比分统计应用"
else
    for pid in $pids; do
        kill $pid
        echo "已停止进程: $pid"
    done
    echo "比分统计应用已停止"
fi
