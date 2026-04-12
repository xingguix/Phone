#!/bin/bash

# 检查pip是否安装
if ! command -v pip &> /dev/null; then
    echo "错误: pip 未安装，请先安装pip"
    exit 1
fi

# 使用国内镜像安装依赖
echo "正在使用国内镜像安装依赖..."
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if [ $? -eq 0 ]; then
    echo "依赖安装成功！"
else
    echo "依赖安装失败，请检查网络连接或requirements.txt文件"
    exit 1
fi