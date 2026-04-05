<#
.SYNOPSIS
    Shared helper module for Fabric REST API operations.
.DESCRIPTION
    Provides common functions for authentication, config management,
    and Fabric API calls used across all deployment scripts.
#>

function Get-FabricToken {
    <#
    .SYNOPSIS
        Obtain a bearer token for the specified Azure resource via az CLI.
    .PARAMETER Resource
        The token audience (default: https://api.fabric.microsoft.com).
    #>
    [CmdletBinding()]
    param(
        [string]$Resource = "https://api.fabric.microsoft.com"
    )
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $token = az account get-access-token --resource $Resource --query accessToken -o tsv 2>$errFile
        $azErr = Get-Content $errFile -Raw -ErrorAction SilentlyContinue
    } finally {
        Remove-Item $errFile -ErrorAction SilentlyContinue
    }

    if (-not $token) {
        if ($azErr -match "AADSTS700082|AADSTS50076|AADSTS50173|expired") {
            Write-Error "Token expired or requires re-authentication. Run 'az login' to refresh."
        } elseif ($azErr -match "az login") {
            Write-Error "Not logged in. Run 'az login' first."
        } else {
            Write-Error "Failed to obtain token for '$Resource'. Error: $azErr"
        }
        throw "Authentication failed"
    }
    return $token
}

function Get-FabricHeaders {
    <#
    .SYNOPSIS
        Build HTTP headers with bearer token for the given resource.
    #>
    [CmdletBinding()]
    param(
        [string]$Resource = "https://api.fabric.microsoft.com"
    )
    $token = Get-FabricToken -Resource $Resource
    return @{
        "Authorization" = "Bearer $token"
        "Content-Type"  = "application/json"
    }
}

function Get-Config {
    <#
    .SYNOPSIS
        Read and parse config.json from the repository root.
    #>
    [CmdletBinding()]
    param(
        [string]$ConfigPath
    )
    if (-not $ConfigPath) {
        $ConfigPath = Join-Path (Split-Path -Parent $PSScriptRoot) "config.json"
    }
    if (-not (Test-Path $ConfigPath)) {
        Write-Error "Config file not found: $ConfigPath"
        throw "Config not found"
    }
    return Get-Content $ConfigPath -Raw | ConvertFrom-Json
}

function Save-Config {
    <#
    .SYNOPSIS
        Write config object back to config.json.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Config,
        [string]$ConfigPath
    )
    if (-not $ConfigPath) {
        $ConfigPath = Join-Path (Split-Path -Parent $PSScriptRoot) "config.json"
    }
    $Config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath -Encoding UTF8
    Write-Host "  config.json updated." -ForegroundColor Green
}

function Invoke-FabricApi {
    <#
    .SYNOPSIS
        Call a Fabric REST API endpoint with automatic retry on 429/503.
    .PARAMETER Uri
        Full API URL.
    .PARAMETER Method
        HTTP method (default: GET).
    .PARAMETER Body
        Request body (will be serialized to JSON if not already a string).
    .PARAMETER Headers
        HTTP headers (obtained via Get-FabricHeaders).
    .PARAMETER MaxRetries
        Maximum retry attempts for transient errors (default: 3).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Uri,
        [string]$Method = "GET",
        [object]$Body,
        [hashtable]$Headers,
        [int]$MaxRetries = 3
    )
    if (-not $Headers) {
        $Headers = Get-FabricHeaders
    }

    $attempt = 0
    while ($true) {
        $attempt++
        try {
            $params = @{
                Uri     = $Uri
                Method  = $Method
                Headers = $Headers
            }
            if ($Body) {
                if ($Body -is [string]) {
                    $params.Body = $Body
                } else {
                    $params.Body = $Body | ConvertTo-Json -Depth 10
                }
            }
            $response = Invoke-RestMethod @params
            return $response
        }
        catch {
            $statusCode = $null
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }

            # Retry on 429 (throttled) or 503 (service unavailable)
            if ($statusCode -in @(429, 503) -and $attempt -le $MaxRetries) {
                $retryAfter = 5 * $attempt
                if ($_.Exception.Response.Headers -and $_.Exception.Response.Headers["Retry-After"]) {
                    $retryAfter = [int]$_.Exception.Response.Headers["Retry-After"]
                }
                Write-Warning "HTTP $statusCode — retrying in ${retryAfter}s (attempt $attempt/$MaxRetries)..."
                Start-Sleep -Seconds $retryAfter
                continue
            }

            # Re-authenticate hint on 401
            if ($statusCode -eq 401) {
                Write-Error "HTTP 401 Unauthorized. Your token may have expired — run 'az login' and retry."
            }

            throw
        }
    }
}

function Find-OrCreateItem {
    <#
    .SYNOPSIS
        Find an existing Fabric item by display name and type, or create it.
    .PARAMETER WorkspaceId
        Workspace GUID.
    .PARAMETER DisplayName
        Item display name.
    .PARAMETER ItemType
        Fabric item type (Lakehouse, Eventhouse, Ontology, etc.).
    .PARAMETER Description
        Item description (used on create).
    .PARAMETER Headers
        HTTP headers with auth token.
    .PARAMETER ApiBase
        Fabric API base URL.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$WorkspaceId,
        [Parameter(Mandatory)][string]$DisplayName,
        [Parameter(Mandatory)][string]$ItemType,
        [string]$Description = "",
        [hashtable]$Headers,
        [string]$ApiBase = "https://api.fabric.microsoft.com/v1"
    )
    if (-not $Headers) { $Headers = Get-FabricHeaders }

    $items = (Invoke-FabricApi -Uri "$ApiBase/workspaces/$WorkspaceId/items" -Headers $Headers).value
    $existing = $items | Where-Object { $_.displayName -eq $DisplayName -and $_.type -eq $ItemType }
    if ($existing) {
        Write-Host "  [EXISTS] $ItemType '$DisplayName' = $($existing.id)" -ForegroundColor Yellow
        return $existing
    }

    $body = @{
        displayName = $DisplayName
        type        = $ItemType
        description = $Description
    }
    $created = Invoke-FabricApi -Uri "$ApiBase/workspaces/$WorkspaceId/items" -Method Post -Headers $Headers -Body $body
    Write-Host "  [CREATED] $ItemType '$DisplayName' = $($created.id)" -ForegroundColor Green
    return $created
}

Export-ModuleMember -Function Get-FabricToken, Get-FabricHeaders, Get-Config, Save-Config, Invoke-FabricApi, Find-OrCreateItem
