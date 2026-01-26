# Must-Check Golden Cases

`cases_highest_priority.json` is the most critical dataset in this folder. When running any golden-case regression tests, always make sure this file is processed first and that its expected tags are aligned with the current tags before proceeding to `cases1.json`, `cases2.json`, or any other suites.

Treat this file as the sync point for `dynamic_over_control` changes: any change to the tagging logic must keep these cases passing before broader batches are considered clean.
