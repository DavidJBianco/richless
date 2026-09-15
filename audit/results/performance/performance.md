# Interactive performance observations

| Lines | Input | Path | First display (s) | End reached (s) | Reported max RSS (MiB) | Trials |
|---:|---|---|---:|---:|---:|---:|
| 100 | file | filter | 0.105–0.375 | 0.181–0.451 | 31.6–31.9 | 3 |
| 100 | file | plain | 0.052–0.055 | 0.131–0.132 | 1.6–1.6 | 3 |
| 100 | file | wrapper | 0.106–0.483 | 0.187–0.561 | 31.4–31.6 | 3 |
| 100 | pipe | filter | 0.054–0.055 | 0.131–0.135 | 1.9–1.9 | 3 |
| 100 | pipe | plain | 0.051–0.055 | 0.131–0.136 | 1.9–1.9 | 3 |
| 100 | pipe | wrapper | 0.106–0.378 | 0.183–0.458 | 31.3–31.6 | 3 |
| 10,000 | file | filter | 1.848–1.998 | 1.979–2.129 | 361.4–361.6 | 3 |
| 10,000 | file | plain | 0.053–0.055 | 0.128–0.136 | 1.7–1.7 | 3 |
| 10,000 | file | wrapper | 1.841–2.006 | 1.970–2.137 | 361.4–363.4 | 3 |
| 10,000 | pipe | filter | 0.054–0.055 | 0.131–0.135 | 3.2–3.2 | 3 |
| 10,000 | pipe | plain | 0.054–0.055 | 0.133–0.136 | 3.2–3.2 | 3 |
| 10,000 | pipe | wrapper | 1.842–1.998 | 1.969–2.124 | 361.5–364.8 | 3 |
| 166,000 | file | filter | 30.474–30.848 | 31.744–32.127 | 5585.6–5585.6 | 3 |
| 166,000 | file | plain | 0.053–0.055 | 0.184–0.191 | 1.7–1.7 | 3 |
| 166,000 | file | wrapper | 30.465–30.696 | 31.682–31.970 | 5584.2–5585.0 | 3 |
| 166,000 | pipe | filter | 0.053–0.055 | 0.240–0.243 | 28.8–28.8 | 3 |
| 166,000 | pipe | plain | 0.051–0.055 | 0.241–0.242 | 28.8–28.9 | 3 |
| 166,000 | pipe | wrapper | 30.484–30.800 | 31.755–32.026 | 5584.1–5585.6 | 3 |
| 500,000 | file | filter | >=45.01 | unavailable (deadline) | unavailable (deadline) | 1 |
| 500,000 | file | plain | 0.051–0.055 | 0.295–0.299 | 1.7–1.7 | 3 |
| 500,000 | file | wrapper | >=45.00 | unavailable (deadline) | unavailable (deadline) | 1 |
| 500,000 | pipe | filter | 0.055–0.055 | 0.514–0.518 | 84.3–84.3 | 3 |
| 500,000 | pipe | plain | 0.051–0.055 | 0.508–0.512 | 84.3–84.3 | 3 |
| 500,000 | pipe | wrapper | >=45.00 | unavailable (deadline) | unavailable (deadline) | 1 |

First-display resolution is approximately 50 ms. End times include command synchronization.
RSS is wait4 child accounting, not aggregate simultaneous process-tree memory. Deadline-killed
sessions cannot reliably account for descendant RSS and are marked unavailable.
The filter-only pipe control does not invoke richless: ordinary |LESSOPEN skips stdin.
