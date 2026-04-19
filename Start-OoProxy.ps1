<#
.SYNOPSIS
    ooProxy Auto-Start — Inicia o servidor ooProxy junto com o Windows.

.DESCRIPTION
    Gerencia chaves API com criptografia forte (Windows DPAPI) e inicia o
    servidor proxy ooProxy.  Se já existir uma chave no formato antigo
    (XOR fraco em ~/.ooProxy/keys.json), ela é decriptada e reencriptada
    com DPAPI antes de iniciar.

.PARAMETER Install
    Registra este script para executar ao fazer logon no Windows (Scheduled Task).

.PARAMETER Uninstall
    Remove a tarefa agendada de auto-start.

.PARAMETER Reset
    Apaga as chaves armazenadas e solicita novas.

.PARAMETER Silent
    Executa sem janela de console visível (usado pela tarefa agendada).

.EXAMPLE
    .\Start-OoProxy.ps1                 # Inicia normalmente
    .\Start-OoProxy.ps1 -Install        # Registra no startup do Windows
    .\Start-OoProxy.ps1 -Uninstall      # Remove do startup
    .\Start-OoProxy.ps1 -Reset          # Reconfigura chaves
#>

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ═══════════════════════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════════════════════
$SCRIPT_PATH   = $MyInvocation.MyCommand.Path
$PROJECT_DIR   = Split-Path -Parent $SCRIPT_PATH
$OOPROXY_DIR   = Join-Path $env:USERPROFILE ".ooproxy"
$KEYS_FILE     = Join-Path $OOPROXY_DIR "keys"
$LOG_FILE      = Join-Path $OOPROXY_DIR "startup.log"
$OLD_KEYS_FILE = Join-Path (Join-Path $env:USERPROFILE ".ooProxy") "keys.json"
$VENV_PYTHON   = Join-Path $PROJECT_DIR "venv\Scripts\python.exe"
$TASK_NAME     = "ooProxy-AutoStart"

# ═══════════════════════════════════════════════════════════
#  Logging
# ═══════════════════════════════════════════════════════════
function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [ConsoleColor]$Color = [ConsoleColor]::White
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$timestamp] [$Level] $Message"

    # Always write to log file
    if (-not (Test-Path $OOPROXY_DIR)) {
        New-Item -ItemType Directory -Path $OOPROXY_DIR -Force | Out-Null
    }
    Add-Content -Path $LOG_FILE -Value $entry -Encoding UTF8

    # Write to console if interactive
    if ([Environment]::UserInteractive -and $Host.UI.RawUI) {
        Write-Host $entry -ForegroundColor $Color
    }
}

function Write-Banner {
    param([string]$Text)
    $line = "=" * 50
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host $line -ForegroundColor Cyan
    Write-Host ""
}

# ═══════════════════════════════════════════════════════════
#  DPAPI Encryption (forte — vinculada ao usuário Windows)
# ═══════════════════════════════════════════════════════════
function Protect-ApiKey {
    <# Criptografa uma string usando DPAPI (Data Protection API).
       Só pode ser decriptada pelo mesmo usuário no mesmo computador. #>
    param([string]$PlainText)
    $secure = ConvertTo-SecureString $PlainText -AsPlainText -Force
    return ConvertFrom-SecureString $secure
}

function Unprotect-ApiKey {
    <# Decripta uma string DPAPI de volta para texto plano. #>
    param([string]$EncryptedText)
    $secure = ConvertTo-SecureString $EncryptedText
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

# ═══════════════════════════════════════════════════════════
#  Decriptação do formato antigo (XOR fraco do projeto)
# ═══════════════════════════════════════════════════════════
function Get-XorKeyStream {
    <# Reproduz _keystream() de key_store.py — SHA256 counter-mode. #>
    param([string]$Seed, [int]$Size)
    $stream = [System.Collections.Generic.List[byte]]::new()
    $counter = 0
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        while ($stream.Count -lt $Size) {
            $data = [System.Text.Encoding]::UTF8.GetBytes("${Seed}:${counter}")
            $hash = $sha.ComputeHash($data)
            $stream.AddRange($hash)
            $counter++
        }
    }
    finally {
        $sha.Dispose()
    }
    return , $stream.GetRange(0, $Size).ToArray()
}

function Get-NormalizedEndpoint {
    <# Reproduz normalize_endpoint() de key_store.py. #>
    param([string]$RawEndpoint)
    $raw = ($RawEndpoint -as [string]).Trim()
    if (-not $raw) { return "" }

    if ($raw -notmatch "://" -and -not $raw.StartsWith("//")) {
        $candidate = "//${raw}"
    }
    else {
        $candidate = $raw
    }

    try {
        $uri = [uri]$candidate
        $hostPart = $uri.Host.ToLower()
        if (-not $hostPart) {
            return $raw.TrimEnd('/').ToLower()
        }
        if ($uri.Port -gt 0 -and -not $uri.IsDefaultPort) {
            return "${hostPart}:$($uri.Port)"
        }
        return $hostPart
    }
    catch {
        return $raw.TrimEnd('/').ToLower()
    }
}

function Decrypt-LegacyKey {
    <# Decripta uma chave no formato v1: (XOR com keystream SHA256). #>
    param(
        [string]$Endpoint,
        [string]$Value
    )
    if (-not $Value.StartsWith("v1:")) {
        throw "Formato de chave não suportado: $($Value.Substring(0, [Math]::Min(6, $Value.Length)))..."
    }

    $encoded = $Value.Substring(3)

    # URL-safe base64 → standard base64
    $encoded = $encoded.Replace('-', '+').Replace('_', '/')
    $padding = (4 - ($encoded.Length % 4)) % 4
    if ($padding -lt 4) { $encoded += ('=' * $padding) }

    $encrypted = [Convert]::FromBase64String($encoded)
    $secret = Get-XorKeyStream -Seed $Endpoint -Size $encrypted.Length

    $payload = [byte[]]::new($encrypted.Length)
    for ($i = 0; $i -lt $encrypted.Length; $i++) {
        $payload[$i] = $encrypted[$i] -bxor $secret[$i]
    }

    return [System.Text.Encoding]::UTF8.GetString($payload)
}

# ═══════════════════════════════════════════════════════════
#  Salvar / Carregar chaves DPAPI
# ═══════════════════════════════════════════════════════════
function Save-Keys {
    param(
        [string]$Url,
        [hashtable]$Entries,  # endpoint → apiKey (plain)
        [string]$Note = "saved"
    )
    if (-not (Test-Path $OOPROXY_DIR)) {
        New-Item -ItemType Directory -Path $OOPROXY_DIR -Force | Out-Null
    }

    $encEntries = @{}
    foreach ($ep in $Entries.Keys) {
        $encEntries[$ep] = Protect-ApiKey $Entries[$ep]
    }

    $data = @{
        version   = "v2-dpapi"
        url       = $Url
        entries   = $encEntries
        timestamp = (Get-Date -Format "o")
    }

    $data | ConvertTo-Json -Depth 4 | Set-Content $KEYS_FILE -Encoding UTF8
    Write-Log "Keys $Note → $KEYS_FILE" "OK" Green
}

function Load-Keys {
    <# Retorna @{ url, entries = @{ endpoint → plainKey } } ou $null. #>
    if (-not (Test-Path $KEYS_FILE)) { return $null }

    try {
        $raw = Get-Content $KEYS_FILE -Raw | ConvertFrom-Json

        if ($raw.version -ne "v2-dpapi") {
            Write-Log "Versão desconhecida no keys file: $($raw.version)" "WARN" Yellow
            return $null
        }

        $entries = @{}
        foreach ($prop in $raw.entries.PSObject.Properties) {
            $entries[$prop.Name] = Unprotect-ApiKey $prop.Value
        }

        return @{
            url     = $raw.url
            entries = $entries
        }
    }
    catch {
        Write-Log "Falha ao decriptar keys (pode pertencer a outro usuário): $_" "WARN" Yellow
        return $null
    }
}

# ═══════════════════════════════════════════════════════════
#  Migrar chaves legadas (v1 XOR → v2 DPAPI)
# ═══════════════════════════════════════════════════════════
function Migrate-LegacyKeys {
    <# Lê ~/.ooProxy/keys.json, decripta com XOR, reencripta com DPAPI. #>
    if (-not (Test-Path $OLD_KEYS_FILE)) { return $null }

    Write-Log "Encontrado keys.json legado, migrando para DPAPI..." "INFO" Cyan

    try {
        $oldData = Get-Content $OLD_KEYS_FILE -Raw | ConvertFrom-Json
        $entries = @{}
        $endpointList = @()

        foreach ($prop in $oldData.PSObject.Properties) {
            $endpoint = Get-NormalizedEndpoint $prop.Name
            if (-not $endpoint) { continue }
            try {
                $plain = Decrypt-LegacyKey -Endpoint $endpoint -Value $prop.Value
                $entries[$endpoint] = $plain
                $endpointList += $endpoint
                Write-Log "  Decriptada chave para: $endpoint" "OK" Green
            }
            catch {
                Write-Log "  Falha ao decriptar chave para $endpoint`: $_" "WARN" Yellow
            }
        }

        if ($entries.Count -eq 0) {
            Write-Log "Nenhuma chave válida encontrada no keys.json legado." "WARN" Yellow
            return $null
        }

        # Selecionar endpoint
        $selectedEndpoint = $null
        if ($entries.Count -eq 1) {
            $selectedEndpoint = $endpointList[0]
        }
        else {
            Write-Host ""
            Write-Host "Múltiplas chaves encontradas:" -ForegroundColor Cyan
            for ($i = 0; $i -lt $endpointList.Count; $i++) {
                Write-Host "  [$($i + 1)] $($endpointList[$i])" -ForegroundColor White
            }
            $choice = Read-Host "Selecione o endpoint padrão [1-$($entries.Count)]"
            $idx = [int]$choice - 1
            if ($idx -lt 0 -or $idx -ge $endpointList.Count) { $idx = 0 }
            $selectedEndpoint = $endpointList[$idx]
        }

        # Reconstruir URL
        $defaultUrl = "https://$selectedEndpoint/v1"
        Write-Host ""
        $inputUrl = Read-Host "URL completa da API [$defaultUrl]"
        if (-not $inputUrl) { $inputUrl = $defaultUrl }

        # Salvar com DPAPI
        Save-Keys -Url $inputUrl -Entries $entries -Note "migrado de keys.json"

        return @{
            url      = $inputUrl
            entries  = $entries
            endpoint = $selectedEndpoint
        }
    }
    catch {
        Write-Log "Falha na migração: $_" "ERROR" Red
        return $null
    }
}

# ═══════════════════════════════════════════════════════════
#  Solicitar chave ao usuário
# ═══════════════════════════════════════════════════════════
function Prompt-ForKey {
    Write-Banner "ooProxy — Configuração Inicial"

    $defaultUrl = "https://integrate.api.nvidia.com/v1"

    Write-Host "Backends suportados:" -ForegroundColor DarkGray
    Write-Host "  - NVIDIA NIM:    https://integrate.api.nvidia.com/v1" -ForegroundColor DarkGray
    Write-Host "  - OpenAI:        https://api.openai.com/v1" -ForegroundColor DarkGray
    Write-Host "  - Groq:          https://api.groq.com/openai/v1" -ForegroundColor DarkGray
    Write-Host "  - Together AI:   https://api.together.xyz/v1" -ForegroundColor DarkGray
    Write-Host "  - OpenRouter:    https://openrouter.ai/api/v1" -ForegroundColor DarkGray
    Write-Host ""

    $url = Read-Host "URL base da API [$defaultUrl]"
    if (-not $url) { $url = $defaultUrl }

    $apiKey = $null
    do {
        $secureKey = Read-Host "Chave da API (API Key)" -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        }
        finally {
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }

        if (-not $apiKey) {
            Write-Host '[ERRO] A chave nao pode ser vazia.' -ForegroundColor Red
        }
    } while (-not $apiKey)

    $endpoint = Get-NormalizedEndpoint $url
    $entries = @{ $endpoint = $apiKey }

    Save-Keys -Url $url -Entries $entries -Note "configuração inicial"

    Write-Host ""
    Write-Host "[OK] Chave criptografada com DPAPI e salva." -ForegroundColor Green
    Write-Host "     Arquivo: $KEYS_FILE" -ForegroundColor DarkGray
    Write-Host ""

    return @{
        url      = $url
        entries  = $entries
        endpoint = $endpoint
    }
}

# ═══════════════════════════════════════════════════════════
#  Install / Uninstall (Tarefa Agendada)
# ═══════════════════════════════════════════════════════════
if ($Install) {
    Write-Banner "ooProxy — Instalação no Startup"

    $psArgs = "-ExecutionPolicy Bypass -WindowStyle Minimized -File `"$SCRIPT_PATH`""

    $action   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs
    $trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1)

    Register-ScheduledTask `
        -TaskName $TASK_NAME `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Inicia o servidor ooProxy automaticamente ao fazer logon." `
        -Force | Out-Null

    Write-Host "[OK] ooProxy registrado para iniciar com o Windows." -ForegroundColor Green
    Write-Host "     Nome da tarefa:  $TASK_NAME" -ForegroundColor DarkGray
    Write-Host "     Script:          $SCRIPT_PATH" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Para remover:  .\Start-OoProxy.ps1 -Uninstall" -ForegroundColor DarkGray
    exit 0
}

if ($Uninstall) {
    $exists = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
    if ($exists) {
        Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
        Write-Host "[OK] Tarefa '$TASK_NAME' removida." -ForegroundColor Green
    }
    else {
        Write-Host "[INFO] Tarefa '$TASK_NAME' não encontrada." -ForegroundColor Yellow
    }
    exit 0
}

# ═══════════════════════════════════════════════════════════
#  Reset
# ═══════════════════════════════════════════════════════════
if ($Reset) {
    if (Test-Path $KEYS_FILE) {
        Remove-Item $KEYS_FILE -Force
        Write-Log "Chaves DPAPI removidas." "OK" Yellow
        Write-Host "[OK] Chaves removidas. Reconfigurando..." -ForegroundColor Yellow
    }
}

# ═══════════════════════════════════════════════════════════
#  MAIN — Resolver chave e iniciar servidor
# ═══════════════════════════════════════════════════════════
$config = $null

# 1. Tentar carregar chaves DPAPI existentes
$config = Load-Keys
if ($config) {
    Write-Log "Chaves DPAPI carregadas com sucesso." "OK" Green
}

# 2. Se não encontrou, tentar migrar do formato antigo (v1 XOR)
if (-not $config) {
    $config = Migrate-LegacyKeys
}

# 3. Se ainda não tem, pedir ao usuário
if (-not $config) {
    # Se não é interativo, não podemos pedir — logar e sair
    if (-not [Environment]::UserInteractive) {
        Write-Log "Nenhuma chave configurada e sessão não é interativa. Execute o script manualmente primeiro." "ERROR" Red
        exit 1
    }
    $config = Prompt-ForKey
}

if (-not $config) {
    Write-Log "Falha ao obter chaves. Abortando." "ERROR" Red
    exit 1
}

# Identificar URL e chave a usar
$serverUrl = $config.url
$endpoint  = Get-NormalizedEndpoint $serverUrl
$apiKey    = $config.entries[$endpoint]

if (-not $apiKey) {
    # Se o endpoint da URL não bate com nenhuma entry, pegar a primeira
    $firstKey = ($config.entries.GetEnumerator() | Select-Object -First 1)
    if ($firstKey) {
        $apiKey = $firstKey.Value
        Write-Log "Usando chave do endpoint: $($firstKey.Key)" "INFO" Cyan
    }
}

if (-not $apiKey) {
    Write-Log "Nenhuma chave disponível para $serverUrl" "ERROR" Red
    exit 1
}

# ═══════════════════════════════════════════════════════════
#  Iniciar o servidor
# ═══════════════════════════════════════════════════════════
Write-Log "Iniciando ooProxy..." "INFO" Cyan

$pythonExe = if (Test-Path $VENV_PYTHON) { $VENV_PYTHON } else { "python" }
$ooproxyScript = Join-Path $PROJECT_DIR "ooproxy.py"

if (-not (Test-Path $ooproxyScript)) {
    Write-Log "ooproxy.py não encontrado em: $PROJECT_DIR" "ERROR" Red
    exit 1
}

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║           ooProxy está rodando           ║" -ForegroundColor Cyan
Write-Host "  ╠══════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "  ║  Backend:  $($serverUrl.PadRight(29)) ║" -ForegroundColor White
Write-Host "  ║  Local:    http://127.0.0.1:11434        ║" -ForegroundColor White
Write-Host "  ║  Ctrl+C para parar                       ║" -ForegroundColor DarkGray
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Log "Python: $pythonExe" "INFO" DarkGray
Write-Log "Backend: $serverUrl" "INFO" DarkGray
Write-Log "Escutando em: http://127.0.0.1:11434" "INFO" DarkGray

try {
    & $pythonExe $ooproxyScript --serve --url $serverUrl --key $apiKey
}
catch {
    Write-Log "Servidor encerrado com erro: $_" "ERROR" Red
    exit 1
}
finally {
    # Limpar a chave da memória
    $apiKey = $null
    [GC]::Collect()
    Write-Log "Servidor encerrado." "INFO" Cyan
}
