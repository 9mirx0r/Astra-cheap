# Selective command-output filtering

Use this reference only when large shell output is a recurring cost.

Prefer native bounded queries first, such as `git status --short`, `git diff --stat`, and scoped `rg -n` searches. A diff summary helps locate changes; read the actual patch before reviewing correctness.

## Optional RTK

The [upstream README](https://github.com/rtk-ai/rtk#supported-ai-tools), reviewed on 2026-09-07, documents Windows binaries and a Codex integration through AGENTS.md and RTK.md instructions. That does not establish automatic interception of this host's PowerShell exec_command tool.

Check availability once per host, not per task:

```powershell
Get-Command rtk -ErrorAction SilentlyContinue
```

If absent, continue with native commands. Do not install or run global initialization as part of an ordinary task.

If available, inspect its version and help. First compare an explicit, read-only `rtk git status` with `git status --short` on a stable repository. Verify that relevant paths and states survive. This comparison validates only that command and version.

Before adopting a test filter, check both passing and failing cases, including the exit code and recoverable full diagnostics. Keep raw evidence when acceptance requires it. Do not rerun expensive or mutating commands merely to compare formatting. On ambiguity, use the original output.

Do not prefix arbitrary PowerShell pipelines or mutation commands. RTK is optional; a filter failure is not a successful underlying task. Its estimated output reductions are not subscription quota measurements.

## Local observation

On 2026-09-07, Get-Command returned no RTK executable in this host's PATH. No RTK command or runtime integration was tested, and no installation or configuration change was made. Native filtering remains the active path.
