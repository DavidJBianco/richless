"""Build an audit ledger from retained per-scenario JSON records."""

import argparse
from collections import Counter
import json
import re
from pathlib import Path


def main() -> None:
    """Write a readable ledger and compact machine-readable summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    latest = {}
    for path in sorted(args.directory.glob('test_*.json')):
        record = json.loads(path.read_text())
        record['artifact'] = path.name
        previous = latest.get(record['id'])
        if previous is None or path.stat().st_mtime_ns > previous[0]:
            latest[record['id']] = (path.stat().st_mtime_ns, record)
    records = [latest[key][1] for key in sorted(latest)]
    counts = Counter(r['status'] for r in records)
    lines = ['# Scenario ledger', '', 'Counts: ' + json.dumps(dict(counts), sort_keys=True), '',
             '| Scenario | Status | Unmet expectation / note |', '|---|---|---|']
    for r in records:
        failures = [c['expectation'] for c in r['checks'] if not c['pass']]
        note = '; '.join(failures) or r.get('product_decision', r.get('exception', 'All recorded expectations met'))
        note = note.replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| [{r['id']}]({r['artifact']}) | {r['status']} | {note} |")
    (args.directory / 'ledger.md').write_text('\n'.join(lines) + '\n')
    (args.directory / 'summary.json').write_text(json.dumps({'counts': dict(counts), 'scenarios': len(records)}, indent=2))
    measured = [r for r in records if 'measurements' in r and r['id'].startswith('test_audit_performance')]
    if measured:
        rows = ['# Interactive performance observations', '',
                '| Lines | Input | Path | First display (s) | End reached (s) | Reported max RSS (MiB) | Trials |',
                '|---:|---|---|---:|---:|---:|---:|']
        def order(record: dict) -> tuple:
            match = re.search(r'\[(\d+)-(file|pipe)-(plain|filter|wrapper)\]', record['id'])
            return (int(match[1]), match[2], match[3])
        for r in sorted(measured, key=order):
            count, route, mode = order(r)
            samples = r['measurements']
            if any(m.get('censored') for m in samples):
                first = '>=' + format(samples[-1]['first_display_seconds_lower_bound'], '.2f')
                end = rss = 'unavailable (deadline)'
            else:
                firsts = [m['first_display_seconds'] for m in samples]
                ends = [m['end_seconds'] for m in samples]
                first = f'{min(firsts):.3f}–{max(firsts):.3f}'
                end = f'{min(ends):.3f}–{max(ends):.3f}'
                memory = [m['maxrss_native'] / (1024 ** 2 if m['rss_units'] == 'bytes' else 1024)
                          for m in samples if m.get('maxrss_native') is not None]
                rss = f'{min(memory):.1f}–{max(memory):.1f}' if memory else 'unavailable'
            rows.append(f'| {count:,} | {route} | {mode} | {first} | {end} | {rss} | {len(samples)} |')
        rows += ['', 'First-display resolution is approximately 50 ms. End times include command synchronization.',
                 'RSS is wait4 child accounting, not aggregate simultaneous process-tree memory. Deadline-killed',
                 'sessions cannot reliably account for descendant RSS and are marked unavailable.',
                 'Inspect each record’s LESSOPEN template: historical | filters skip stdin; current |- filters process it.']
        (args.directory / 'performance.md').write_text('\n'.join(rows) + '\n')
    print(json.dumps({'counts': dict(counts), 'scenarios': len(records)}, indent=2))


if __name__ == '__main__':
    main()
