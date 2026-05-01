@echo off
chcp 65001 >nul
echo ========================================
echo  数据库初始化脚本
echo ========================================
echo.

:: 检查 MySQL 是否安装
mysql --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 MySQL 客户端
    echo 请确保 MySQL 已安装并配置好 PATH
    pause
    exit /b 1
)

echo [1/2] 创建数据库和授权...
mysql -u root -p123456 -e "
CREATE DATABASE IF NOT EXISTS kui_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON kui_db.* TO 'root'@'%' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON kui_db.* TO 'root'@'localhost' IDENTIFIED BY '123456';
FLUSH PRIVILEGES;
" 2>nul

if errorlevel 1 (
    echo [错误] 数据库创建失败，请检查 MySQL 用户名密码
    pause
    exit /b 1
)

echo [2/2] 测试连接...
mysql -u root -p123456 -e "USE kui_db; SHOW TABLES;" 2>nul
if errorlevel 1 (
    echo [错误] 数据库连接测试失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo  数据库初始化完成！
echo ========================================
echo.
echo 现在可以启动服务了，运行 start.bat
echo.
pause
