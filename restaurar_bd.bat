@echo off
chcp 65001 >nul
echo ============================================================
echo   RESTAURACION DE BASE DE DATOS - Sistema de Titulacion ITA
echo   Contraseña de todos los usuarios: admin12345!
echo ============================================================
echo.

REM ─── CONFIGURACION ──────────────────────────────────────────
REM Edita estos valores segun la configuracion del equipo destino
set PG_BIN="C:\Program Files\PostgreSQL\17\bin"
set PG_HOST=localhost
set PG_PORT=5432
set PG_USER=%PG_USER%
if "%PG_USER%"=="" set PG_USER=belyview
set PG_PASS=%PGPASSWORD%
set DB_NAME=titulacion_2026
set BACKUP_FILE=backup_titulacion_2026_FINAL.dump

if "%PG_PASS%"=="" (
    echo [ERROR] Define la variable de entorno PGPASSWORD antes de ejecutar.
    pause
    exit /b 1
)

REM ─── VERIFICAR QUE EXISTE EL BACKUP ────────────────────────
if not exist "%BACKUP_FILE%" (
    echo [ERROR] No se encontro el archivo de backup: %BACKUP_FILE%
    echo Asegurate de que el archivo .dump esta en la misma carpeta que este script.
    pause
    exit /b 1
)

echo [1/4] Verificando conexion a PostgreSQL...
set PGPASSWORD=%PG_PASS%
%PG_BIN%\psql.exe -h %PG_HOST% -p %PG_PORT% -U %PG_USER% -d postgres -c "SELECT version();" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se pudo conectar a PostgreSQL.
    echo Verifica que PostgreSQL este corriendo y que las credenciales sean correctas.
    echo Host: %PG_HOST%  Puerto: %PG_PORT%  Usuario: %PG_USER%
    pause
    exit /b 1
)
echo [OK] Conexion exitosa.
echo.

echo [2/4] Eliminando base de datos existente "%DB_NAME%"...
echo        (Si no existe, esto es normal)
%PG_BIN%\psql.exe -h %PG_HOST% -p %PG_PORT% -U %PG_USER% -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '%DB_NAME%' AND pid <> pg_backend_pid();" >nul 2>&1
%PG_BIN%\dropdb.exe -h %PG_HOST% -p %PG_PORT% -U %PG_USER% --if-exists %DB_NAME%
echo [OK] Base de datos eliminada (o no existia).
echo.

echo [3/4] Creando base de datos nueva "%DB_NAME%"...
%PG_BIN%\createdb.exe -h %PG_HOST% -p %PG_PORT% -U %PG_USER% -E UTF8 %DB_NAME%
if errorlevel 1 (
    echo [ERROR] No se pudo crear la base de datos.
    pause
    exit /b 1
)
echo [OK] Base de datos creada.
echo.

echo [4/4] Restaurando datos desde %BACKUP_FILE%...
echo        Esto puede tardar unos segundos...
%PG_BIN%\pg_restore.exe -h %PG_HOST% -p %PG_PORT% -U %PG_USER% -d %DB_NAME% --no-owner --no-privileges --verbose %BACKUP_FILE% 2>restauracion_log.txt
echo [OK] Restauracion completada.
echo.

echo ============================================================
echo   RESTAURACION EXITOSA
echo ============================================================
echo.
echo   Base de datos: %DB_NAME%
echo   Servidor:      %PG_HOST%:%PG_PORT%
echo   Usuario BD:    %PG_USER%
echo.
echo   Contraseña de TODOS los usuarios del sistema: admin12345!
echo.
echo   Usuarios principales:
echo     - adminITA     (Administrador)
echo     - academico    (Division de Estudios)
echo     - escolares    (Servicios Escolares)
echo     - jefe_proy    (Jefe de Proyectos)
echo     - 21370903     (Alumno - Belen)
echo.
echo   El log de restauracion se guardo en: restauracion_log.txt
echo ============================================================
echo.
pause
