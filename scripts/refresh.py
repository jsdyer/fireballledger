#!/usr/bin/env python3
"""One serial, cached JPL collection per run. Publish validated captures atomically."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = 'https://ssd-api.jpl.nasa.gov/fireball.api'
ALLOWED = {'date-min', 'date-max', 'energy-min', 'energy-max', 'impact-e-min', 'impact-e-max', 'alt-min', 'alt-max', 'req-loc', 'req-alt', 'req-vel-comp', 'vel-comp', 'sort', 'limit'}
REQUIRED = {'date', 'energy', 'impact-e', 'lat', 'lat-dir', 'lon', 'lon-dir', 'alt'}

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def configuration(config):
    params = config['apiParameters']
    if not isinstance(params, dict) or set(params) - ALLOWED:
        raise ValueError('Unsupported API parameters')
    if not 2 <= config['retainCaptures'] <= 104:
        raise ValueError('retainCaptures must be 2–104')
    if not 1 <= config['minimumRecords'] <= config['maximumRecords'] <= 100000:
        raise ValueError('Record limits are invalid')
    if not 0 <= config['maximumDropFraction'] < 1:
        raise ValueError('Drop guard must be in [0,1)')
    if not isinstance(config['acceptedApiVersions'], list) or not config['acceptedApiVersions']:
        raise ValueError('Set accepted API versions after reviewing the API documentation')
    if not config.get('userAgent', '').startswith('CoolCode-FireballLedger/') or 'contact:' not in config['userAgent']:
        raise ValueError('Use the application-specific User-Agent with a contact')
    return params

def normalize(payload, config):
    if payload.get('signature', {}).get('version') not in config['acceptedApiVersions']:
        raise ValueError('API version changed; review its documentation before accepting it')
    fields = payload.get('fields', [])
    if not isinstance(fields, list) or len(set(fields)) != len(fields) or not REQUIRED.issubset(fields):
        raise ValueError('Missing/duplicate API fields')
    rows = payload.get('data')
    if not isinstance(rows, list) or int(payload.get('count', -1)) != len(rows):
        raise ValueError('Reported row count does not match response')
    if not config['minimumRecords'] <= len(rows) <= config['maximumRecords']:
        raise ValueError('Unexpected number of records; last good capture retained')
    records, keys = [], set()
    for row in rows:
        if len(row) != len(fields):
            raise ValueError('Incomplete row')
        record = dict(zip(fields, row))
        key = record['date']
        if not isinstance(key, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', key):
            raise ValueError('Invalid event time')
        datetime.strptime(key, '%Y-%m-%d %H:%M:%S')
        if key in keys:
            raise ValueError('Duplicate event time; review matching strategy')
        keys.add(key)
        for field in fields:
            if field not in ('date', 'lat-dir', 'lon-dir') and record[field] is not None:
                number = float(record[field])
                if not math.isfinite(number):
                    raise ValueError('Nonfinite source number')
                if field in ('energy', 'impact-e') and number <= 0:
                    raise ValueError('Energy must be positive')
        if record['energy'] is None or record['impact-e'] is None:
            raise ValueError('Missing required energies')
        coords = [record[x] for x in ('lat', 'lat-dir', 'lon', 'lon-dir')]
        if any(x is None for x in coords) and not all(x is None for x in coords):
            raise ValueError('Partial coordinate set')
        if coords[0] is not None and not (0 <= float(coords[0]) <= 90 and 0 <= float(coords[2]) <= 180 and coords[1] in ('N','S') and coords[3] in ('E','W')):
            raise ValueError('Invalid coordinate')
        records.append(record)
    return sorted(records, key=lambda r:r['date'], reverse=True)

def differences(previous, current):
    old = {r['date']: r for r in previous}
    new = {r['date']: r for r in current}
    return {
        'added': sorted(new.keys() - old.keys(), reverse=True),
        'absent': sorted(old.keys() - new.keys(), reverse=True),
        'changed': [{'date': k, 'fields': [{'field': f, 'before': old[k].get(f), 'after': new[k].get(f)} for f in sorted(old[k].keys() | new[k].keys()) if old[k].get(f) != new[k].get(f)]} for k in sorted(old.keys() & new.keys(), reverse=True) if old[k] != new[k]],
    }

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as temp:
        json.dump(value, temp, separators=(',', ':'), ensure_ascii=False)
        temp.write('\n')
        temporary = Path(temp.name)
    temporary.replace(path)

def retain(payload, config, directory, captured_at=None):
    params = configuration(config)
    records = normalize(payload, config)
    captured_at = captured_at or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    scope = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    index_path = directory / 'index.json'
    index = read(index_path) if index_path.exists() else {'schema': 'coolcode.fireball.index.v1', 'captures': []}
    prior_meta = index['captures'][0] if index['captures'] else None
    prior = read(directory / prior_meta['file']) if prior_meta else None
    comparable = prior is not None and prior['scope'] == scope
    if comparable and len(records) < len(prior['records']) * (1 - config['maximumDropFraction']):
        raise ValueError('Unexpected catalogue shrinkage; last good capture retained')
    delta = differences(prior['records'], records) if comparable else None
    snap = {'schema': 'coolcode.fireball.capture.v1', 'capturedAt': captured_at, 'source': API, 'sourceUrl': API + '?' + urlencode(params), 'signature': payload['signature'], 'fields': payload['fields'], 'parameters': params, 'scope': scope, 'records': records, 'previousCapturedAt': prior['capturedAt'] if comparable else None, 'comparison': delta}
    name = 'captures/' + captured_at.replace(':', '').replace('-', '') + '.json'
    meta = {'file': name, 'capturedAt': captured_at, 'count': len(records), 'located': sum(r['lat'] is not None for r in records), 'earliest': records[-1]['date'], 'latest': records[0]['date'], 'comparison': {k:len(v) for k,v in delta.items()} if delta is not None else None}
    captures = [meta] + [c for c in index['captures'] if c['file'] != name]
    keep = captures[:config['retainCaptures']]
    atomic(directory / name, snap)
    atomic(index_path, {'schema': index['schema'], 'captures': keep})
    atomic(directory / 'status.json', {'retrieved_at': captured_at, 'records': len(records), 'located': meta['located'], 'through': meta['latest'], 'captures': len(keep)})
    for old in captures[config['retainCaptures']:]:
        (directory / old['file']).unlink(missing_ok=True)
    return meta

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, help='Validate a previously downloaded official JSON response instead of requesting the API')
    args = parser.parse_args()
    config = read(ROOT / 'web/config.json')
    params = configuration(config)
    if args.input:
        payload = read(args.input)
    else:
        request = Request(API + '?' + urlencode(params), headers={'User-Agent':config['userAgent'], 'Accept':'application/json'})
        with urlopen(request, timeout=60) as response:
            content = response.read(12_000_001)
            if len(content) > 12_000_000: raise ValueError('API response exceeds size limit')
            payload = json.loads(content)
    result = retain(payload, config, ROOT / 'web/data')
    print(f"Retained {result['count']} events, {result['located']} with coordinates, captured {result['capturedAt']}")

if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'Capture failed; last good deployment remains available: {exc}')
