@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM =============================================================================
REM Stock Data Service - データバックアップスクリプト (Windows用)
REM MongoDBのデータをエクスポートする (定期バックアップ・システム移行兼用)
REM =============================================================================

REM ----- 設定 -----
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "BACKUP_BASE_DIR=%PROJECT_DIR%\backups"

REM 日時を取得 (YYYYMMDD_HHMMSS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list 2^>nul') do set "DT=%%I"
set "DATE=%DT:~0,4%%DT:~4,2%%DT:~6,2%_%DT:~8,2%%DT:~10,2%%DT:~12,2%"
set "BACKUP_NAME=stock_data_migration_%DATE%"

if "%MONGO_USERNAME%"=="" set "MONGO_USERNAME=admin"
if "%MONGO_PASSWORD%"=="" set "MONGO_PASSWORD=password"
if "%DATABASE_NAME%"=="" set "DATABASE_NAME=stock_data"
if "%RETENTION_DAYS%"=="" set "RETENTION_DAYS=30"

REM バックアップモード (デフォルト: all)
set "BACKUP_MODE=%~1"
if "%BACKUP_MODE%"=="" set "BACKUP_MODE=all"

REM ----- ヘルプ -----
if "%BACKUP_MODE%"=="-h" goto :usage
if "%BACKUP_MODE%"=="--help" goto :usage
if "%BACKUP_MODE%"=="/?" goto :usage

REM ----- バリデーション -----
if not "%BACKUP_MODE%"=="all" if not "%BACKUP_MODE%"=="data" (
    echo [ERROR] 無効なバックアップモード: %BACKUP_MODE% ^(all または data を指定してください^)
    goto :usage
)

REM ----- docker compose コマンドの検出 -----
set "COMPOSE_CMD="
docker compose version >nul 2>&1
if %errorlevel%==0 (
    set "COMPOSE_CMD=docker compose"
) else (
    docker-compose --version >nul 2>&1
    if %errorlevel%==0 (
        set "COMPOSE_CMD=docker-compose"
    ) else (
        echo [ERROR] docker compose が見つかりません。Docker Composeをインストールしてください。
        exit /b 1
    )
)

REM ----- メイン処理 -----
echo === Stock Data Service データバックアップ ===
echo バックアップモード: %BACKUP_MODE%
echo データベース: %DATABASE_NAME%

REM MongoDBコンテナの起動確認
cd /d "%PROJECT_DIR%"
echo MongoDBコンテナの状態を確認中...
%COMPOSE_CMD% exec -T mongo mongosh --eval "db.adminCommand('ping')" --quiet >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MongoDBコンテナが起動していません。先に 'docker compose up -d mongo' を実行してください。
    exit /b 1
)

REM バックアップディレクトリを作成
if not exist "%BACKUP_BASE_DIR%" mkdir "%BACKUP_BASE_DIR%"

REM 一時ディレクトリを作成
set "TEMP_DIR=%TEMP%\stock_backup_%DATE%"
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%\%BACKUP_NAME%"

echo 一時ディレクトリ: %TEMP_DIR%

REM コレクションの選定
if "%BACKUP_MODE%"=="data" (
    set "COLLECTIONS=daily_prices stock_info financials"
    echo 対象コレクション: daily_prices, stock_info, financials
) else (
    set "COLLECTIONS=users api_keys daily_prices stock_info financials"
    echo 対象コレクション: users, api_keys, daily_prices, stock_info, financials
)

REM コンテナ内の一時ディレクトリをクリーンアップ
%COMPOSE_CMD% exec -T mongo rm -rf /tmp/migration_backup >nul 2>&1

REM 各コレクションをダンプ
echo MongoDBからデータをエクスポート中...
for %%C in (%COLLECTIONS%) do (
    echo   エクスポート中: %%C
    %COMPOSE_CMD% exec -T mongo mongodump --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin --db="%DATABASE_NAME%" --collection=%%C --out="/tmp/migration_backup" --quiet
    if !errorlevel! neq 0 (
        echo [ERROR] %%C のエクスポートに失敗しました
        goto :cleanup_error
    )
)

REM コンテナからホストにコピー
echo バックアップデータをコンテナからコピー中...
for /f "tokens=*" %%I in ('%COMPOSE_CMD% ps -q mongo') do set "CONTAINER_ID=%%I"
docker cp "%CONTAINER_ID%:/tmp/migration_backup/%DATABASE_NAME%" "%TEMP_DIR%\%BACKUP_NAME%\"
if %errorlevel% neq 0 (
    echo [ERROR] コンテナからのコピーに失敗しました
    goto :cleanup_error
)

REM コンテナ内の一時ファイルをクリーンアップ
%COMPOSE_CMD% exec -T mongo rm -rf /tmp/migration_backup >nul 2>&1

REM メタデータファイルを作成
(
    echo {
    echo     "backup_date": "%DT:~0,4%-%DT:~4,2%-%DT:~6,2%T%DT:~8,2%:%DT:~10,2%:%DT:~12,2%",
    echo     "backup_mode": "%BACKUP_MODE%",
    echo     "database_name": "%DATABASE_NAME%",
    echo     "collections": ["%COLLECTIONS: =", "%"]
    echo }
) > "%TEMP_DIR%\%BACKUP_NAME%\backup_metadata.json"

REM コレクション統計情報
echo コレクション統計情報を取得中...
for %%C in (%COLLECTIONS%) do (
    for /f "tokens=*" %%N in ('%COMPOSE_CMD% exec -T mongo mongosh --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin --quiet --eval "db.getSiblingDB('%DATABASE_NAME%').%%C.countDocuments({})"') do (
        echo   %%C: %%N documents
    )
)

REM tar.gzに圧縮
echo バックアップを圧縮中...
set "BACKUP_FILE=%BACKUP_BASE_DIR%\%BACKUP_NAME%.tar.gz"
tar -czf "%BACKUP_FILE%" -C "%TEMP_DIR%" "%BACKUP_NAME%"
if %errorlevel% neq 0 (
    echo [ERROR] 圧縮に失敗しました
    goto :cleanup_error
)

REM 一時ファイルをクリーンアップ
rmdir /s /q "%TEMP_DIR%" 2>nul

REM バックアップの整合性チェック
if /i "%CHECK_BACKUP%"=="true" (
    echo バックアップの整合性チェック中...
    tar -tzf "%BACKUP_FILE%" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] 整合性チェックに失敗しました
        exit /b 1
    )
    echo 整合性チェック: OK
)

REM 古いバックアップを削除（保持期間を超えたもの）
if %RETENTION_DAYS% gtr 0 (
    echo 古いバックアップを確認中 ^(%RETENTION_DAYS%日以上前^)...
    forfiles /p "%BACKUP_BASE_DIR%" /m "stock_data_migration_*.tar.gz" /d -%RETENTION_DAYS% /c "cmd /c echo   削除: @file && del @path" 2>nul
)

REM バックアップサイズ
for %%F in ("%BACKUP_FILE%") do set "BACKUP_SIZE=%%~zF"
set /a "BACKUP_SIZE_KB=%BACKUP_SIZE% / 1024"
set /a "BACKUP_SIZE_MB=%BACKUP_SIZE_KB% / 1024"

echo.
echo === バックアップ完了 ===
echo 出力ファイル: %BACKUP_FILE%
if %BACKUP_SIZE_MB% gtr 0 (
    echo ファイルサイズ: 約 %BACKUP_SIZE_MB% MB
) else (
    echo ファイルサイズ: 約 %BACKUP_SIZE_KB% KB
)
echo.
echo リストア方法:
echo   scripts\restore_data.bat %BACKUP_NAME%.tar.gz

exit /b 0

:cleanup_error
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" 2>nul
%COMPOSE_CMD% exec -T mongo rm -rf /tmp/migration_backup >nul 2>&1
exit /b 1

:usage
echo Usage: %~nx0 [all^|data]
echo.
echo   all   - 全コレクションをバックアップ (デフォルト)
echo           (users, api_keys, daily_prices, stock_info, financials)
echo   data  - 株価データのみバックアップ (users, api_keysを除外)
echo           (daily_prices, stock_info, financials)
echo.
echo Examples:
echo   %~nx0          # 全データをバックアップ
echo   %~nx0 all      # 全データをバックアップ
echo   %~nx0 data     # 株価データのみバックアップ
echo.
echo Environment variables:
echo   MONGO_USERNAME   - MongoDB username (default: admin)
echo   MONGO_PASSWORD   - MongoDB password (default: password)
echo   DATABASE_NAME    - Database name (default: stock_data)
echo   RETENTION_DAYS   - 古いバックアップの保持日数 (default: 30, 0で無効)
echo   CHECK_BACKUP     - 整合性チェックを実行 (true/false, default: false)
exit /b 0
