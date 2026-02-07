@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM =============================================================================
REM Stock Data Service - データリストアスクリプト (Windows用)
REM バックアップからMongoDBにデータを復元する (システム移行用)
REM =============================================================================

REM ----- 設定 -----
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "BACKUP_BASE_DIR=%PROJECT_DIR%\backups"

if "%MONGO_USERNAME%"=="" (set "MONGO_USERNAME=admin")
if "%MONGO_PASSWORD%"=="" (set "MONGO_PASSWORD=password")
if "%DATABASE_NAME%"=="" (set "DATABASE_NAME=stock_data")

REM リストアモード (デフォルト: merge)
set "BACKUP_FILE=%~1"
set "RESTORE_MODE=%~2"
if "%RESTORE_MODE%"=="" (set "RESTORE_MODE=merge")

REM ----- ヘルプ -----
if "%BACKUP_FILE%"=="-h" goto :usage
if "%BACKUP_FILE%"=="--help" goto :usage
if "%BACKUP_FILE%"=="/?" goto :usage
if "%BACKUP_FILE%"=="" goto :usage

REM ----- バリデーション -----
if not "%RESTORE_MODE%"=="merge" if not "%RESTORE_MODE%"=="replace" (
    echo [ERROR] 無効なリストアモード: %RESTORE_MODE% ^(merge または replace を指定してください^)
    goto :usage
)

REM バックアップファイルのパスを解決
set "BACKUP_PATH="
if exist "%BACKUP_FILE%" (
    set "BACKUP_PATH=%BACKUP_FILE%"
) else if exist "%BACKUP_BASE_DIR%\%BACKUP_FILE%" (
    set "BACKUP_PATH=%BACKUP_BASE_DIR%\%BACKUP_FILE%"
) else (
    echo [ERROR] バックアップファイルが見つかりません: %BACKUP_FILE%
    echo.
    echo backups ディレクトリ内のバックアップ:
    if exist "%BACKUP_BASE_DIR%\stock_data_migration_*.tar.gz" (
        dir /b "%BACKUP_BASE_DIR%\stock_data_migration_*.tar.gz"
    ) else (
        echo   バックアップが見つかりません
    )
    exit /b 1
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
echo === Stock Data Service データリストア ===
echo バックアップファイル: %BACKUP_PATH%
echo リストアモード: %RESTORE_MODE%
echo データベース: %DATABASE_NAME%

REM replaceモードの確認
if "%RESTORE_MODE%"=="replace" (
    echo.
    echo WARNING: replaceモードでは対象コレクションの既存データが全て削除されます。
    set /p "CONFIRM=続行しますか? (y/N): "
    if /i not "!CONFIRM!"=="y" (
        echo リストアを中止しました。
        exit /b 0
    )
)

REM MongoDBコンテナの起動確認
cd /d "%PROJECT_DIR%"
echo MongoDBコンテナの状態を確認中...
%COMPOSE_CMD% exec -T mongo mongosh --eval "db.adminCommand('ping')" --quiet >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MongoDBコンテナが起動していません。先に 'docker compose up -d mongo' を実行してください。
    exit /b 1
)

REM 日時を取得 (一時ディレクトリ名用)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list 2^>nul') do set "DT=%%I"
set "TIMESTAMP=%DT:~0,14%"

REM 一時ディレクトリを作成
set "TEMP_DIR=%TEMP%\stock_restore_%TIMESTAMP%"
if exist "%TEMP_DIR%" (rmdir /s /q "%TEMP_DIR%")
mkdir "%TEMP_DIR%"

echo バックアップを展開中: %TEMP_DIR%
tar -xzf "%BACKUP_PATH%" -C "%TEMP_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] バックアップの展開に失敗しました
    goto :cleanup_error
)

REM 展開されたディレクトリを探す
set "EXTRACTED_DIR="
for /d %%D in ("%TEMP_DIR%\stock_data_migration_*") do set "EXTRACTED_DIR=%%D"
if "%EXTRACTED_DIR%"=="" (
    echo [ERROR] バックアップの展開に失敗しました。正しいバックアップファイルか確認してください。
    goto :cleanup_error
)

REM メタデータを表示
if exist "%EXTRACTED_DIR%\backup_metadata.json" (
    echo バックアップ情報:
    type "%EXTRACTED_DIR%\backup_metadata.json"
    echo.
)

REM BSONデータのディレクトリを確認
set "BSON_DIR=%EXTRACTED_DIR%\%DATABASE_NAME%"
if not exist "%BSON_DIR%" (
    REM DATABASE_NAMEと異なる名前でダンプされている場合を探す
    for /d %%D in ("%EXTRACTED_DIR%\*") do (
        if exist "%%D\*.bson" set "BSON_DIR=%%D"
    )
)
if not exist "%BSON_DIR%\*.bson" (
    echo [ERROR] バックアップ内にBSONデータが見つかりません。
    goto :cleanup_error
)

echo BSONデータ: %BSON_DIR%

REM リストア対象コレクションを特定
set "COLLECTIONS="
for %%F in ("%BSON_DIR%\*.bson") do (
    set "COL_NAME=%%~nF"
    set "COLLECTIONS=!COLLECTIONS! !COL_NAME!"
)

if "%COLLECTIONS%"=="" (
    echo [ERROR] リストア対象のコレクションが見つかりません。
    goto :cleanup_error
)

echo リストア対象コレクション:%COLLECTIONS%

REM replaceモードの場合、対象コレクションを削除
if "%RESTORE_MODE%"=="replace" (
    echo 既存コレクションを削除中...
    for %%C in (%COLLECTIONS%) do (
        echo   削除中: %%C
        %COMPOSE_CMD% exec -T mongo mongosh --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin --quiet --eval "db.getSiblingDB('%DATABASE_NAME%').%%C.drop()"
    )
)

REM BSONデータをコンテナにコピー
echo データをMongoDBコンテナにコピー中...
for /f "tokens=*" %%I in ('%COMPOSE_CMD% ps -q mongo') do set "CONTAINER_ID=%%I"
%COMPOSE_CMD% exec -T mongo rm -rf /tmp/migration_restore >nul 2>&1
docker cp "%BSON_DIR%" "%CONTAINER_ID%:/tmp/migration_restore"
if %errorlevel% neq 0 (
    echo [ERROR] コンテナへのコピーに失敗しました
    goto :cleanup_error
)

REM mongorestoreを実行
echo データを復元中...
for %%C in (%COLLECTIONS%) do (
    echo   復元中: %%C
    if "%RESTORE_MODE%"=="merge" (
        %COMPOSE_CMD% exec -T mongo mongorestore --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin --db="%DATABASE_NAME%" --collection=%%C --noIndexRestore "/tmp/migration_restore/%%C.bson" 2>&1 || echo   ^(%%C: 一部の重複ドキュメントはスキップされました^)
    ) else (
        %COMPOSE_CMD% exec -T mongo mongorestore --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin --db="%DATABASE_NAME%" --collection=%%C --noIndexRestore "/tmp/migration_restore/%%C.bson"
        if !errorlevel! neq 0 (
            echo [ERROR] %%C の復元に失敗しました
            goto :cleanup_error
        )
    )
)

REM インデックスを再作成
echo インデックスを再作成中...
%COMPOSE_CMD% exec -T mongo mongosh --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin /docker-entrypoint-initdb.d/mongo-init.js >nul 2>&1
if %errorlevel% neq 0 (
    echo (インデックス作成: 一部は既に存在するためスキップ)
)

REM 復元結果の確認
echo 復元結果を確認中...
for %%C in (%COLLECTIONS%) do (
    for /f "tokens=*" %%N in ('%COMPOSE_CMD% exec -T mongo mongosh --username="%MONGO_USERNAME%" --password="%MONGO_PASSWORD%" --authenticationDatabase=admin --quiet --eval "db.getSiblingDB('%DATABASE_NAME%').%%C.countDocuments({})"') do (
        echo   %%C: %%N documents
    )
)

REM クリーンアップ
%COMPOSE_CMD% exec -T mongo rm -rf /tmp/migration_restore >nul 2>&1
if exist "%TEMP_DIR%" (rmdir /s /q "%TEMP_DIR%" 2>nul)

echo.
echo === リストア完了 ===
echo.
echo 注意事項:
echo   - users/api_keysを復元した場合、移行元のJWT_SECRET_KEYも移行先に設定してください
echo   - 移行先でアプリケーションを再起動してください: docker compose restart web

exit /b 0

:cleanup_error
%COMPOSE_CMD% exec -T mongo rm -rf /tmp/migration_restore >nul 2>&1
if exist "%TEMP_DIR%" (rmdir /s /q "%TEMP_DIR%" 2>nul)
exit /b 1

:usage
echo Usage: %~nx0 ^<backup_file^> [merge^|replace]
echo.
echo   backup_file - バックアップファイル名 (backups\ 内のtar.gzファイル)
echo   merge       - 既存データに追加/更新 (デフォルト、重複キーはスキップ)
echo   replace     - 対象コレクションを削除してから復元
echo.
echo Examples:
echo   %~nx0 stock_data_migration_20250101_120000.tar.gz
echo   %~nx0 stock_data_migration_20250101_120000.tar.gz merge
echo   %~nx0 stock_data_migration_20250101_120000.tar.gz replace
echo.
echo Available backups:
if exist "%BACKUP_BASE_DIR%\stock_data_migration_*.tar.gz" (
    dir /b "%BACKUP_BASE_DIR%\stock_data_migration_*.tar.gz"
) else (
    echo   バックアップが見つかりません
)
echo.
echo Environment variables:
echo   MONGO_USERNAME  - MongoDB username (default: admin)
echo   MONGO_PASSWORD  - MongoDB password (default: password)
echo   DATABASE_NAME   - Database name (default: stock_data)
exit /b 0
