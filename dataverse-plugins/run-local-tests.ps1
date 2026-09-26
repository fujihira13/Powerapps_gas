$ErrorActionPreference = 'Stop'

$pluginCli = Get-Command pac -ErrorAction Stop
$pluginCliRoot = Split-Path -Parent $pluginCli.Source
$sdkAssembly = Get-ChildItem -Path (Join-Path $pluginCliRoot 'Microsoft.PowerApps.CLI.*') -Directory |
    ForEach-Object { Join-Path $_.FullName 'tools\Microsoft.Xrm.Sdk.dll' } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Sort-Object -Descending |
    Select-Object -First 1

if (-not $sdkAssembly) {
    throw 'Could not locate Microsoft.Xrm.Sdk.dll beneath the local PAC CLI installation.'
}

$testsProject = Join-Path $PSScriptRoot 'RequiredFields.Plugin.Tests\RequiredFields.Plugin.Tests.csproj'
$configFile = Join-Path $PSScriptRoot 'NuGet.Config'
$outputExe = Join-Path $PSScriptRoot 'RequiredFields.Plugin.Tests\bin\Debug\net48\RequiredFields.Plugin.Tests.exe'

dotnet restore $testsProject --configfile $configFile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

dotnet build $testsProject --no-restore -p:DataverseSdkAssemblyPath=$sdkAssembly
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $outputExe
exit $LASTEXITCODE
