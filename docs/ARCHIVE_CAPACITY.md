# Bounded archive capacity recovery

The 250,000,000-byte compressed working-tree ceiling was an application guard,
not a GitHub quota. It blocked persistence after collection on November 22, 2026.
The allowance is now 500,000,000 bytes, with warnings at 400,000,000 bytes.
No files or Git history are pruned; original SHA-256 integrity checks, immutable
record checks, and the 30 MB uncompressed individual-file limit remain intact.

Each successful save writes reports/storage-health.json and storage-health.md
with actual compressed bytes, file count, remaining capacity, and thresholds.
At the warning threshold the workflow emits a warning; over the hard limit it
still fails and refuses to advance the manifest. Save/push failures remain fatal.

This is bounded headroom, not a long-term storage migration. These measurements
exclude Git history. Review both working-tree growth and repository history and
plan external archival storage before 400 MB; no paid service is activated here.

Previously failed runs' unsaved observations are not claimed recovered. Later
collections use their real observation times. Forecasts and protocols do not
change, and missed issuance remains recorded.
