param([Parameter(Mandatory=$true)][string]$Exe, [Parameter(Mandatory=$true)][string]$ReportDirectory)
$ErrorActionPreference = 'Stop'
$testReport = Join-Path $ReportDirectory 'frozen-selftest.json'
$networkReport = Join-Path $ReportDirectory 'runtime-network-audit.json'
if ((Test-Path -LiteralPath $testReport) -or (Test-Path -LiteralPath $networkReport)) { throw 'Reports already exist; choose a new directory.' }
New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
$previousPath = $env:PATH
$previousPythonHome = $env:PYTHONHOME
$previousPythonPath = $env:PYTHONPATH
$samples = 0; $tcp = 0; $udp = 0; $queryFailures = 0
# Establish that endpoint inventory can be read. The current PowerShell PID
# need not own any endpoint; a successful empty inventory is still meaningful.
if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) -or -not (Get-Command Get-NetUDPEndpoint -ErrorAction SilentlyContinue)) { throw 'Endpoint sampling cmdlets unavailable; zero endpoints would not be evidence.' }
Get-NetTCPConnection -ErrorAction Stop | Out-Null
Get-NetUDPEndpoint -ErrorAction Stop | Out-Null
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONHOME = ''; $env:PYTHONPATH = ''
    $runtimeProc = Start-Process -FilePath $Exe -ArgumentList @('--self-test', ('"' + $testReport + '"')) -PassThru -WindowStyle Hidden
    while (-not $runtimeProc.HasExited) {
        $samples++
        try {
            # Read complete inventories then filter. Querying by an endpoint-
            # free PID can itself raise 'no matching objects' on Windows.
            $tcp += @(Get-NetTCPConnection -ErrorAction Stop | Where-Object OwningProcess -EQ $runtimeProc.Id).Count
            $udp += @(Get-NetUDPEndpoint -ErrorAction Stop | Where-Object OwningProcess -EQ $runtimeProc.Id).Count
        } catch { $queryFailures++ }
        Start-Sleep -Milliseconds 250
        $runtimeProc.Refresh()
    }
    $runtimeProc.WaitForExit()
    $exitCode = $runtimeProc.ExitCode
} finally {
    $env:PATH = $previousPath
    $env:PYTHONHOME = $previousPythonHome
    $env:PYTHONPATH = $previousPythonPath
}
$data = @{status=$(if ($queryFailures -eq 0 -and $exitCode -eq 0 -and $tcp -eq 0 -and $udp -eq 0) {'passed'} else {'failed'}); scope='PID TCP/UDP endpoint sampling during public fixture self-test; sanitized PATH/PYTHONHOME/PYTHONPATH'; snapshots=$samples; endpoint_query_failures=$queryFailures; tcp_endpoint_observations=$tcp; udp_endpoint_observations=$udp; exit_code=$exitCode; clean_python_free_vm_tested=$false; physical_network_disconnection_tested=$false; limitations='Sampling can miss short connections/native activity routed via other processes. Python exists on this host but is excluded from child runtime search. No firewall/network settings changed. Inventory readability was checked before launch and query failures are counted; failed sampling is not zero-network proof.'}
$data | ConvertTo-Json | Set-Content -LiteralPath $networkReport -Encoding utf8
if ($exitCode -ne 0) { throw 'Frozen self-test failed; inspect its report.' }
if ($queryFailures -ne 0) { throw 'Endpoint inventory queries failed; absence of observed connections is inconclusive.' }
if ($tcp -ne 0 -or $udp -ne 0) { throw 'Observed unexpected network endpoints; do not publish before review.' }
