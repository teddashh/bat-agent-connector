# Synthetic native transport fixture. It cannot inspect configuration or change hosts.
$ErrorActionPreference='Stop'
$request=[Console]::In.ReadToEnd() | ConvertFrom-Json
if ($request.action -ne 'contract' -or $request.schema_version -ne 1) { exit 1 }
$reply=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'contract.json') -Raw | ConvertFrom-Json
$reply.request_id=$request.request_id
$bytes=[Text.Encoding]::UTF8.GetBytes(($reply | ConvertTo-Json -Depth 8 -Compress))
$stdout=[Console]::OpenStandardOutput()
$stdout.Write($bytes,0,$bytes.Length)
$stdout.Flush()
exit 0
