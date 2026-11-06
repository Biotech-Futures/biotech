#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
export PATH="$HOME/.local/share/mise/installs/node/22.23.2/bin:/Applications/Docker.app/Contents/Resources/bin:$HOME/.docker/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
print '正在启动 BIOTech 演示网站（Admin Analytics + AI chatbot）…'
print '服务就绪后会自动打开独立的 Chrome 窗口，请稍候。'
if python3 -u demo.py start; then
  exit 0
else
  demo_exit_code=$?
  print ''
  print '启动失败。请查看上方错误；如果 Docker 未运行，请先打开 Docker Desktop。'
  print '演示地址：http://127.0.0.1:5187/#/analytics'
  if [[ -t 0 ]]; then
    read -r '?按回车关闭此窗口…'
  fi
  exit "$demo_exit_code"
fi
