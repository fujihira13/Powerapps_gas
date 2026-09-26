# C08 local candidate review

**Status: Canvas MCP validation passed for all six YAML files; Studio save and runtime tests have not been performed.** All candidate `.pa.yaml` changes are in `workspace/Screen1.pa.yaml`. The other five YAML files are the unchanged current-app sync. No case rows, Excel files, flows, or publication settings were changed.

## Candidate behavior

1. Take the submitted row's `cr6cb_evidencecaseid` GUID from `Form1.LastSubmit`.
2. Refresh the table and read that row back by its GUID. Continue only if the row is returned and its `Attachments` table has exactly one item.
3. Apply the existing initial status values, then refresh and read the row and attachment count again.
4. Patch the current queue row in `colT001Metadata` and verify the returned `QueueId`, `SaveStatus`, and `EvidenceCaseId`.
5. Only after that local queue patch is verified, mark the item `保存済み`, bind `varT001Saved`/`varEvidenceCase`, clear a matching fallback ID, and reset the form.
6. On any attempted-save error, missing row, attachment count other than one, status mismatch, or local queue patch mismatch, mark only the saving queue's `SaveStatus` as `保存結果不明`, keep its selection/form state, and show `保存状況を確認しています`. If the form is locally invalid before `SubmitForm`, do not submit; show its validation feedback and keep the queue in its current unsaved state. `OnFailure` checks `Form1.Valid`: when false, it clears only the pending-save lock and preserves the queue/form without setting Unknown; when true or otherwise ambiguous, it follows the Unknown path.
7. If the per-queue unknown marker cannot be written or verified, retain `varT001UnknownQueueId` as a fallback whole-app safety brake. Saves and starts are then blocked until that fallback is resolved. A normal per-queue unknown does not set this fallback, so another queue can continue independently.
8. The save button's `OnSelect` rejects both an unknown or already-saved selected queue and any attempt while the fallback brake is set, even if invoked despite its disabled `DisplayMode`. It requires `Form1.Valid` and accepts only numeric whole values from 1 through Dataverse Whole Number's documented standard ceiling (2,147,483,647). This is a storage type bound, not a business maximum. Conversion uses `IfError(Value(...), Blank())`, fractional inputs are rejected with `Mod(..., 1)`, the form card Update and selection-change handler both use `IfError`, and invalid unsaved values are retained as blank instead of raising a conversion error. Inline validation distinguishes nonnumeric, fractional, below-minimum, and above-standard-maximum input. The final table's configured column bounds have not been read back, so any narrower custom maximum remains unverified. Cancellation is also blocked for the unknown queue. Queue labels read the per-item status.
9. Start continues to select only queue items whose `SaveStatus` is `保存済み`; per-item unknown queues are excluded. The fallback brake blocks starting if an unknown marker could not be recorded.

## Assumptions and gaps

- MCP schema read confirms `cr6cb_evidencecaseid` is a GUID primary key and `{Attachments}` is a `LazyTable`. Canvas compile passed, but `CountRows` on the returned attachment table, `Refresh` visibility timing, and delegation behavior remain unverified at runtime.
- The candidate proves presence/count of one attachment related through the returned case row; it does not compare attachment content or filename.
- Each `Refresh`, `LookUp`, and `CountRows` result has a separate error boundary. A failed refresh cannot fall through to a successful lookup/count sequence, and the readback-success flags are set only after the relevant individual operations succeed.
- The local metadata `Patch` is checked before `varT001UnknownQueueId` is cleared or `ResetForm` runs. A missing/mismatched/error result leaves the queue and form intact and blocked.
- Per-queue unknown state lives in the in-memory `colT001Metadata` collection. It is not restored after app restart. The global ID is only a fallback when writing/verifying that collection failed; in that exceptional state the app blocks other saves and starts because one global ID cannot safely represent multiple unrecorded failures.
- Stable-ID retries remain unimplemented. The current form creates the row before the app receives `LastSubmit`, and no preassigned primary key is written. This candidate does not claim C08 completion or enable a confirmed-failure retry.
- `OnFailure` now attempts the per-queue unknown marker; it uses the global fallback only when that marker cannot be written or verified.

## Local checks

- `python tests/validate_candidate.py` passed: PyYAML parsed all six candidate `.pa.yaml` files; structural comparison against the latest committed readback sync found only the intended save/readback, per-queue unknown, save/cancel gating, and queue-label properties changed; other screens are unchanged; changed Power Fx text has balanced quotes and delimiters; the script checks that numeric conversion is error-handled, integer/min/max predicates are present, the error message surfaces each invalid class, and the branch structure that only the verified path resets the form, unknown paths retain the queue ID, and start filters to saved items.
- These are YAML/lexical checks, not Power Fx compilation or behavioral tests.
- `pac power-fx run` did not return expression results, so no behavior test is claimed. With the user's approval, one Canvas MCP `compile_canvas` call returned `Validation PASSED` for six files. A subsequent `sync_canvas` matched all six candidate files as text; Screen1's raw SHA-256 differed only because the sync used LF and the candidate copy used CRLF. Studio save and real API/runtime tests were not run.

## Review diff

Compare `workspace/Screen1.pa.yaml` with `outputs/canvas-live-readback-20260926-demo-audit/Screen1.pa.yaml`. The diff is limited to `Form1.OnFailure`/`OnSuccess`, save-button gating, intake's global-state clearing, per-item labels, and cancel-button gating. The repeatable local YAML/structure check is `tests/validate_candidate.py`. Microsoft documents that `SubmitForm` validates before sending, does not submit invalid data, and still invokes `OnFailure` for validation failure; candidate logic uses `Form1.Valid` to keep that path out of the Unknown state. Dataverse documents Whole Number’s standard range as -2,147,483,648 through 2,147,483,647 ([column data types](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/create-edit-field-solution-explorer)); the app’s business rule remains only “integer at least 1,” without adding a business-specific upper limit. The formula compiled, but its runtime behavior has not been verified: [SubmitForm reference](https://learn.microsoft.com/en-us/power-platform/power-fx/reference/function-form).
