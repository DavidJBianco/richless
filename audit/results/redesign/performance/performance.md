# Interactive performance observations

| Lines | Input | Path | First display (s) | End reached (s) | Reported max RSS (MiB) | Trials |
|---:|---|---|---:|---:|---:|---:|
| 100 | file | filter | 0.104–0.276 | 0.186–0.356 | 26.6–26.7 | 3 |
| 100 | file | plain | 0.053–0.060 | 0.139–0.149 | 1.6–1.6 | 3 |
| 100 | file | wrapper | 0.154–0.300 | 0.242–0.383 | 26.3–26.5 | 3 |
| 100 | pipe | filter | 0.113–0.228 | 0.203–0.313 | 26.3–26.5 | 3 |
| 100 | pipe | plain | 0.053–0.060 | 0.130–0.143 | 2.0–2.0 | 3 |
| 100 | pipe | wrapper | 0.109–0.286 | 0.198–0.375 | 26.1–26.5 | 3 |
| 10,000 | file | filter | 0.113–0.227 | 0.590–0.714 | 30.2–30.3 | 3 |
| 10,000 | file | plain | 0.054–0.060 | 0.130–0.142 | 1.7–1.7 | 3 |
| 10,000 | file | wrapper | 0.171–0.286 | 0.655–0.825 | 29.9–30.1 | 3 |
| 10,000 | pipe | filter | 0.107–0.225 | 0.480–0.598 | 26.0–26.2 | 3 |
| 10,000 | pipe | plain | 0.052–0.058 | 0.137–0.147 | 3.2–3.2 | 3 |
| 10,000 | pipe | wrapper | 0.151–0.282 | 0.520–0.653 | 26.2–26.3 | 3 |
| 166,000 | file | filter | 0.112–0.266 | 7.457–8.082 | 210.7–210.7 | 3 |
| 166,000 | file | plain | 0.050–0.056 | 0.176–0.187 | 1.7–1.7 | 3 |
| 166,000 | file | wrapper | 0.162–0.281 | 7.560–7.687 | 210.7–210.7 | 3 |
| 166,000 | pipe | filter | 0.114–0.227 | 5.660–6.064 | 210.7–210.7 | 3 |
| 166,000 | pipe | plain | 0.056–0.060 | 0.240–0.265 | 28.8–28.9 | 3 |
| 166,000 | pipe | wrapper | 0.107–0.297 | 5.618–5.726 | 210.7–210.7 | 3 |
| 500,000 | file | filter | 0.156–0.287 | 22.111–22.305 | 632.0–632.0 | 3 |
| 500,000 | file | plain | 0.055–0.060 | 0.317–0.321 | 1.7–1.7 | 3 |
| 500,000 | file | wrapper | 0.234–0.345 | 22.820–23.635 | 632.0–632.0 | 3 |
| 500,000 | pipe | filter | 0.105–0.297 | 15.985–16.475 | 631.9–631.9 | 3 |
| 500,000 | pipe | plain | 0.051–0.060 | 0.468–0.496 | 84.3–84.3 | 3 |
| 500,000 | pipe | wrapper | 0.113–0.345 | 15.441–16.422 | 631.9–631.9 | 3 |

First-display resolution is approximately 50 ms. End times include command synchronization.
RSS is wait4 child accounting, not aggregate simultaneous process-tree memory. Deadline-killed
sessions cannot reliably account for descendant RSS and are marked unavailable.
Inspect each record’s LESSOPEN template: historical | filters skip stdin; current |- filters process it.
