# Read-only oracle copied from reviewed Kit 2ec4b11 client/fleet-desktop-core.ps1.
# Only synthetic fixture paths are supplied through this child process environment.
$ErrorActionPreference='Stop'
function Get-FleetDesktopBinding([string]$inventoryPath,[string]$profileIndexPath,[string]$kitRoot=$PSScriptRoot) {
  $hash=[Security.Cryptography.SHA256]::Create()
  try {
    $text="desktop-configuration-v1`n"
    foreach ($path in @($inventoryPath,$profileIndexPath,(Join-Path $kitRoot 'ssh-config'),(Join-Path (Join-Path $env:USERPROFILE '.ssh') 'config'))) {
      $full=[IO.Path]::GetFullPath($path)
      $text+=[string]$full.Length+':'+$full+':'
      if ([IO.File]::Exists($path)) {
        $digest=([BitConverter]::ToString($hash.ComputeHash([IO.File]::ReadAllBytes($path)))).Replace('-','').ToLowerInvariant()
        $text+='present:'+ $digest+"`n"
      } else { $text+="absent`n" }
    }
    return ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)))).Replace('-','').ToLowerInvariant()
  } finally { $hash.Dispose() }
}

$kitRoot=Join-Path $env:BAT_FLEET_BINDING_FIXTURE 'kit'
$env:USERPROFILE=Join-Path $env:BAT_FLEET_BINDING_FIXTURE ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('5L2/55So6ICF8J+mgA==')))
Get-FleetDesktopBinding (Join-Path $kitRoot 'fleet-inventory.json') (Join-Path $kitRoot 'bat-profiles/index.json') $kitRoot
