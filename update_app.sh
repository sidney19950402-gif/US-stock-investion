#!/bin/bash

# 這個腳本會幫你把最新的修改上傳到 GitHub
# 上傳後，Streamlit Cloud 會自動偵測並更新網頁 (約需 1-2 分鐘)

echo "正在準備更新..."

# 1. 加入所有修改
git add .

# 2. 提交修改 (自動加上日期時間作為備註)
timestamp=$(date "+%Y-%m-%d %H:%M:%S")
git commit -m "Update app: $timestamp"

# 3. 上傳到 GitHub
echo "正在上傳到 GitHub..."
git push

echo "-----------------------------------"
echo "上傳完成！Streamlit 會自動開始更新。"
echo "請等待約 2 分鐘後重新整理網頁。"
