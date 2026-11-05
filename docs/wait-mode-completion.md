# Fork fix: completed rounds with a resident interview process

Imported upstream [PR #846](https://github.com/666ghj/MiroFish/pull/846), commit `689ca11171df363c34fa14dd763467d9757c422a`, authored by sarthaknimbalkar. The original base was upstream `7657031`; this fork applied it to `7e8eb1b`. The import commit retains attribution and the source SHA.

The monitor now completes a run when every enabled platform has emitted `simulation_end`, while keeping the process available for interviews. Completion still waits for the Zep ingestion barrier. A failed drain remains a failure. Later process exit does not overwrite the completed run.

Fork adaptations:

- Persist the selected `platform` in new run states. In parallel mode, wait for both platforms even when the second has not yet created its log. Old run states retain the previous file-based fallback.
- Close/join an old resident interview process before a forced restart deletes its run state, logs and databases. The original PR's start-time helper would otherwise run too late on this API path.

Validation uses simulated processes and providers: the original eight regressions fail before import; new tests reproduce the late-platform and force-cleanup ordering cases before adaptation. The full backend suite passes without paid calls. No new simulation was launched to validate this import.

A running backend must be restarted to load the code. Restarting also closes resident interview processes through the existing shutdown path and finalizes their graph writes. Existing action logs and databases are preserved unless the user explicitly requests a forced restart. The correction does not hot-patch an already running monitor.
