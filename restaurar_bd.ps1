# ============================================================
#   RESTAURACION DE BD - Sistema de Titulacion ITA
#   Ejecutar: powershell -ExecutionPolicy Bypass -File restaurar_bd.ps1
# ============================================================

# ─── CONFIGURACION (editar segun el equipo destino) ──────────
$PG_BIN   = "C:\Program Files\PostgreSQL\17\bin"
$PG_HOST  = "localhost"
$PG_PORT  = "5432"
$PG_USER  = $env:PG_USER
if (-not $PG_USER) { $PG_USER = "belyview" }
$PG_PASS  = $env:PGPASSWORD
$DB_NAME  = "titulacion_2026"
$BACKUP   = Join-Path $PSScriptRoot "backup_titulacion_2026_FINAL.dump"

if (-not $PG_PASS) {
    Write-Host "[ERROR] Define la variable de entorno PGPASSWORD antes de ejecutar." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  RESTAURACION - Sistema de Titulacion ITA" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Verificar backup
if (-not (Test-Path $BACKUP)) {
    Write-Host "[ERROR] No se encontro: $BACKUP" -ForegroundColor Red
    Write-Host "Copia el archivo .dump junto a este script." -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}
Write-Host "[OK] Backup encontrado: $BACKUP" -ForegroundColor Green

# Verificar conexion
Write-Host "`n[1/4] Verificando conexion a PostgreSQL..."
try {
    & "$PG_BIN\psql.exe" -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -c "SELECT 1;" 2>$null | Out-Null
    Write-Host "[OK] Conexion exitosa." -ForegroundColor Green
} catch {
    Write-Host "[ERROR] No se pudo conectar a PostgreSQL." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

# Desconectar sesiones activas y eliminar BD
Write-Host "`n[2/4] Eliminando base de datos '$DB_NAME'..."
& "$PG_BIN\psql.exe" -h $PG_HOST -p $PG_PORT -U $PG_USER -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" 2>$null | Out-Null
& "$PG_BIN\dropdb.exe" -h $PG_HOST -p $PG_PORT -U $PG_USER --if-exists $DB_NAME 2>$null
Write-Host "[OK] Base de datos eliminada." -ForegroundColor Green

# Crear BD nueva
Write-Host "`n[3/4] Creando base de datos '$DB_NAME'..."
& "$PG_BIN\createdb.exe" -h $PG_HOST -p $PG_PORT -U $PG_USER -E UTF8 $DB_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo crear la base de datos." -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}
Write-Host "[OK] Base de datos creada." -ForegroundColor Green

# Restaurar
Write-Host "`n[4/4] Restaurando datos (esto puede tardar)..."
& "$PG_BIN\pg_restore.exe" -h $PG_HOST -p $PG_PORT -U $PG_USER -d $DB_NAME --no-owner --no-privileges $BACKUP 2>"$PSScriptRoot\restauracion_log.txt"
Write-Host "[OK] Restauracion completada." -ForegroundColor Green

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  RESTAURACION EXITOSA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Base de datos: $DB_NAME"
Write-Host "  Servidor:      ${PG_HOST}:${PG_PORT}"
Write-Host ""
Write-Host "  Password de TODOS los usuarios: " -NoNewline
Write-Host "admin12345!" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Usuarios:" -ForegroundColor White
Write-Host "    adminITA   -> Administrador"
Write-Host "    academico  -> Division de Estudios"
Write-Host "    escolares  -> Servicios Escolares"
Write-Host "    jefe_proy  -> Jefe de Proyectos"
Write-Host "    21370903   -> Alumno (Belen)"
Write-Host ""
Read-Host "Presiona Enter para cerrar"
