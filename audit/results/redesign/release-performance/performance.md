# Interactive performance observations

| Lines | Input | Path | First display (s) | End reached (s) | Reported max RSS (MiB) | Trials |
|---:|---|---|---:|---:|---:|---:|
| 100 | file | wrapper | 0.175–0.412 | 0.266–0.495 | 26.5–26.9 | 3 |
| 100 | pipe | wrapper | 0.171–0.340 | 0.262–0.431 | 26.2–26.4 | 3 |
| 10,000 | file | wrapper | 0.167–0.284 | 0.673–0.771 | 30.0–30.1 | 3 |
| 10,000 | pipe | wrapper | 0.107–0.278 | 0.493–0.657 | 26.0–26.1 | 3 |
| 166,000 | file | wrapper | 0.166–0.357 | 7.266–7.635 | 210.7–210.7 | 3 |
| 166,000 | pipe | wrapper | 0.103–0.264 | 5.647–5.826 | 210.7–210.7 | 3 |
| 500,000 | file | wrapper | 0.236–0.407 | 22.143–22.201 | 632.0–632.0 | 3 |
| 500,000 | pipe | wrapper | 0.101–0.342 | 16.740–16.998 | 631.9–631.9 | 3 |

First-display resolution is approximately 50 ms. End times include command synchronization.
RSS is wait4 child accounting, not aggregate simultaneous process-tree memory. Deadline-killed
sessions cannot reliably account for descendant RSS and are marked unavailable.
Inspect each record’s LESSOPEN template: historical | filters skip stdin; current |- filters process it.
