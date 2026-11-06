@echo off
setlocal
cd /d "%~dp0..\frontend-vue"
node local-preview-server.mjs > preview-proxy.log 2> preview-proxy.err.log
