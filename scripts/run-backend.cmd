@echo off
setlocal
cd /d "%~dp0..\backend-java"
if not exist target mkdir target
mvn spring-boot:run > target\backend-run.log 2> target\backend-run.err.log
