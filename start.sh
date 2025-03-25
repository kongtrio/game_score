#!/bin/bash

# 启动SSH隧道管理应用
echo "正在启动SSH隧道管理应用..."

# 检查是否已安装nohup
if ! command -v nohup &> /dev/null; then
    echo "错误: nohup命令不存在，请先安装"
    exit 1
fi

# 检查app.py是否存在
if [ ! -f "game_score_app.py" ]; then
    echo "错误: game_score_app.py文件不存在"
    exit 1
fi

# 后台启动应用
nohup python game_score_app.py > app.log 2>&1 &

# 检查是否启动成功
sleep 2
if ps aux | grep -q 'game_score_app.py'; then
    echo "SSH隧道管理应用已启动，日志输出到app.log"
    echo "PID: $(ps aux | grep '[a]pp.py' | awk '{print $2}')"
else
    echo "启动失败，请检查app.log查看错误信息"
    exit 1
fi
