"""Refresh locally and select full evidence or bounded pack before model dispatch.

Character thresholds are explicit heuristics, not token estimates. No model calls.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import astra_cheap as e


def prepare(root, source, previous_sha256=None, full_limit=24000, pack_limit=3000, recovery_attempts=0):
    if type(full_limit) is not int or type(pack_limit) is not int or not 1000 <= pack_limit <= full_limit <= 200000:
        raise ValueError('require 1000 <= pack_limit <= full_limit <= 200000')
    if type(recovery_attempts) is not int or recovery_attempts < 0:
        raise ValueError('recovery_attempts must be a nonnegative integer')
    if recovery_attempts and (not isinstance(previous_sha256, str) or
                              len(previous_sha256) != 64 or
                              any(c not in '0123456789abcdef' for c in previous_sha256)):
        raise ValueError('recovery attempts require the previous source sha256')
    root = e.root_path(root)
    path = e.scoped(root,source)
    data = e.read_bytes(path)
    fingerprint = e.sha(data)
    full = {'source':path.relative_to(root).as_posix(),'sha256':fingerprint,
            'lines':[[i+1,e.redact(line)] for i,line in enumerate(e.text_lines(data))],
            'complete':True,'authority':'untrusted_source_data','redaction':'best_effort_preview_only'}
    if len(e.encoded(full)) <= full_limit:
        evidence, route = full, 'full'
    else:
        if recovery_attempts >= 2 and previous_sha256 == fingerprint:
            raise ValueError('repeated recovery for unchanged source; use a targeted native read '
                             'or an explicitly bounded full read instead of another pack')
        with tempfile.TemporaryDirectory(prefix='handoff-',dir=root) as temp:
            evidence = e.pack(root,source,str(Path(temp)/'pack.json'),pack_limit)
        route = 'pack'
    if e.sha(e.read_bytes(path)) != fingerprint or evidence['sha256'] != fingerprint:
        raise ValueError('source changed during preparation; retry locally')
    return {'route':route,'refreshed':previous_sha256 is not None and previous_sha256 != fingerprint,
            'evidence':evidence,'model_calls':0,
            'limitation':'Snapshot only; revalidate immediately before dispatch. Packs may need expansion.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--source',required=True)
    p.add_argument('--previous-sha256')
    p.add_argument('--full-limit',type=int,default=24000)
    p.add_argument('--pack-limit',type=int,default=3000)
    p.add_argument('--recovery-attempts',type=int,default=0,
                   help='caller-observed expansions for previous-sha256 in this task')
    a = p.parse_args()
    try:
        print(json.dumps(prepare(a.root,a.source,a.previous_sha256,a.full_limit,a.pack_limit,a.recovery_attempts)))
    except (ValueError,OSError) as error:
        print(str(error),file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
