# Dataverse required-field plug-in candidate

This folder contains one `IPlugin` class in one candidate assembly. It validates the four business columns on Create and Update:

- `cr6cb_environment`: non-empty, non-whitespace string
- `cr6cb_server`: non-empty, non-whitespace string
- `cr6cb_runnumber`: integer greater than or equal to 1
- `cr6cb_targetdate`: non-null `DateTime`

On Update, each value comes from `Target` when that attribute is present; otherwise it comes from the `PreImage` named `PreImage`. An explicit null in `Target` therefore fails even when the old PreImage value was populated. An unrelated-field update is allowed when the current four business values in the PreImage are valid.

The candidate is intentionally not a uniqueness check. The four-column Dataverse alternate key owns duplicate rejection. The local duplicate-tuple case shows only that both tuples satisfy this plug-in's required-value validation. It does not show that Dataverse rejected a duplicate or that the alternate key is active.

## Offline local test

The local test uses the actual `Microsoft.Xrm.Sdk.dll` supplied with the installed PAC CLI and a small fake execution context with synthetic table names. No NuGet packages are referenced or downloaded; the local NuGet configuration clears all package sources. From the repository root, run:

```powershell
.\dataverse-plugins\run-local-tests.ps1
```

The script locates `Microsoft.Xrm.Sdk.dll` under the local PAC CLI installation, restores with `dataverse-plugins\NuGet.Config`, builds, and runs the console test assembly. Alternatively, set the MSBuild property `DataverseSdkAssemblyPath` or environment variable `DATAVERSE_SDK_ASSEMBLY_PATH` to the local SDK DLL path.

This test project targets .NET Framework 4.8 because that local targeting pack and runtime are installed. PAC CLI's plug-in template targets .NET Framework 4.6.2 and normally references `Microsoft.CrmSdk.CoreAssemblies` through NuGet. This offline test does not establish that a `net462` plug-in assembly can be built here, that this candidate can be registered, or that Dataverse executes it. Those remain separate checks and require separate authorization for any cloud changes.

## Registration policy, not performed

The future dedicated fake test table's logical name is not decided yet, so the candidate does not hardcode the existing `cr6cb_evidencecase` table name. The class has no in-code entity allowlist; its intended scope must come from the registered plug-in steps. Do not register it against `cr6cb_evidencecase`, a completion candidate table, or any other table. Registration must remain blocked until the dedicated fake table is separately authorized and created, its actual logical name and column names are read back, and both Create and Update step metadata are checked against that exact table. The Update PreImage must be named `PreImage` and contain the four required columns. If the created schema differs from the candidate's field names, stop and revise the candidate and tests before any registration. An incorrect step registration could apply these checks to another table with matching column names.

No registration, deployment, table creation, API request, flow change, or cloud validation was performed for this candidate.
