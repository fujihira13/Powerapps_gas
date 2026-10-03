param([string]$Configuration = 'Release')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskBuild = Join-Path $taskRoot 'outputs/environment-management-20261003/implementation/build'
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
$taskSigningKey = Join-Path $taskBuild 'management.snk'
if (-not (Test-Path -LiteralPath $taskSigningKey)) {
    $taskRsa = [System.Security.Cryptography.RSACryptoServiceProvider]::new(2048)
    try {
        $taskRsa.PersistKeyInCsp = $false
        [System.IO.File]::WriteAllBytes($taskSigningKey, $taskRsa.ExportCspBlob($true))
    } finally { $taskRsa.Dispose() }
}
$taskReference = Join-Path $env:USERPROFILE '.nuget/packages/microsoft.netframework.referenceassemblies.net462/1.0.0/build/.NETFramework/v4.6.2'
if (-not (Test-Path -LiteralPath $taskReference)) { throw 'The .NET Framework 4.6.2 reference pack is not available.' }
$taskProject = Join-Path $taskRoot 'dataverse-plugins/EnvironmentManagement.Plugin/EnvironmentManagement.Plugin.csproj'
& dotnet build $taskProject --no-restore -c $Configuration "-p:FrameworkPathOverride=$taskReference" "-p:SigningKeyPath=$taskSigningKey"
if ($LASTEXITCODE -ne 0) { throw 'Plugin build failed.' }
$taskAssembly = Join-Path $taskRoot "dataverse-plugins/EnvironmentManagement.Plugin/bin/$Configuration/net462/PowerappsGas.EnvironmentManagement.dll"
$taskIdentity = [System.Reflection.AssemblyName]::GetAssemblyName($taskAssembly)
if ($taskIdentity.GetPublicKeyToken().Length -eq 0) { throw 'Plugin assembly is not signed.' }
Copy-Item -LiteralPath $taskAssembly -Destination (Join-Path $taskBuild 'PowerappsGas.EnvironmentManagement.dll')
$taskAssemblyRegistration = @{
    name = $taskIdentity.Name
    version = $taskIdentity.Version.ToString()
    culture = 'neutral'
    publickeytoken = [System.Convert]::ToHexString($taskIdentity.GetPublicKeyToken()).ToLowerInvariant()
    isolationmode = 2
    sourcetype = 0
    content = [System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes($taskAssembly))
}
$taskAssemblyRegistration | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskBuild 'pluginassembly-create.json') -Encoding utf8
Write-Output ('Signed plugin prepared: ' + $taskIdentity.Name + ', ' + $taskIdentity.Version)
Write-Output 'No upload was performed. Signing key stays in the Git-excluded build folder.'
