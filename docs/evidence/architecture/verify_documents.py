from pathlib import Path
import hashlib
import re

root = Path.cwd()
files = [Path('AGENTS.md'), Path('LICENSE'), *sorted(Path('docs').rglob('*.md'))]
documents = {str(p): p.read_text() for p in files}

def verify(docs):
    errors = []
    anchors = {}
    for name, text in docs.items():
        headings = re.findall(r'^#{1,6} (.+)$', text, re.M)
        ids = [re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-') for heading in headings]
        ids += re.findall(r'<a id="([^"]+)"></a>', text)
        if len(ids) != len(set(ids)):
            errors.append('duplicate anchor: ' + name)
        anchors[name] = set(ids)
    for name, text in docs.items():
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if '://' in target:
                continue
            filename, _, fragment = target.partition('#')
            dest = str(Path(__import__('os').path.normpath(str(Path(name).parent / filename)))) if filename else name
            if dest not in docs:
                if not (root / dest).is_file() or fragment:
                    errors.append('missing local link: ' + name + ' -> ' + target)
            elif fragment and fragment not in anchors[dest]:
                errors.append('missing anchor: ' + name + ' -> ' + target)
    req = re.findall(r'^### ((?:FR|NFR)-\d+)\s*$', docs['docs/requirements.md'], re.M)
    decisions = re.findall(r'^### (DEC-\d+)\s*$', docs['docs/decisions.md'], re.M)
    caps = set(re.findall(r'^\| (CAP-\d+) \|', docs['docs/requirements.md'], re.M))
    d_ids = set(re.findall(r'<a id="(d\d+)"></a>', docs['docs/decisions.md']))
    if len(req) != len(set(req)) or len(decisions) != len(set(decisions)):
        errors.append('duplicate defined identifier')
    rows = re.findall(r'^\| \[((?:FR|NFR)-\d+)\].+$', docs['docs/rtm.md'], re.M)
    if len(rows) != len(set(rows)) or set(rows) != set(req):
        errors.append('requirement/RTM membership mismatch')
    for line in docs['docs/rtm.md'].splitlines():
        if not re.match(r'^\| \[(?:FR|NFR)-', line):
            continue
        cols = line.split('|')
        if len(cols) != 10:
            errors.append('invalid RTM column count')
            continue
        rid = re.search(r'\[((?:FR|NFR)-\d+)\]', cols[1])[1]
        if f'(requirements.md#{rid.lower()})' not in cols[4]:
            errors.append('unanchored acceptance: ' + rid)
        if not set(re.findall(r'CAP-\d+', cols[2])) <= caps:
            errors.append('unknown capability: ' + rid)
        for ref in re.findall(r'\b(?:DEC-\d+|D\d+)\b', cols[3]):
            if ref not in decisions and ref.lower() not in d_ids:
                errors.append('unknown source decision: ' + rid)
    return errors

errors = verify(documents)
if errors:
    raise SystemExit('\n'.join(errors))
print(f'PASS: {len(documents)} document/license files; local links/anchors; unique definitions; {len(re.findall(r'^### (?:FR|NFR)-', documents['docs/requirements.md'], re.M))} requirement/RTM rows; source/capability references')
mutations = {
    'missing file': ('docs/index.md', lambda s: s + '\n[synthetic](missing-document.md)\n'),
    'missing anchor': ('docs/index.md', lambda s: s + '\n[synthetic](requirements.md#missing-anchor)\n'),
    'duplicate ID': ('docs/requirements.md', lambda s: s + '\n### FR-001\n'),
    'missing RTM row': ('docs/rtm.md', lambda s: re.sub(r'^\| \[FR-001\].+\n', '', s, flags=re.M)),
    'unknown source': ('docs/rtm.md', lambda s: s.replace('[D01](decisions.md#d01)', '[D99](decisions.md#d99)', 1)),
    'unknown capability': ('docs/rtm.md', lambda s: s.replace('| CAP-01 |', '| CAP-99 |', 1)),
    'unanchored acceptance': ('docs/rtm.md', lambda s: re.sub(r'(^\| \[FR-001\].*?\| CAP-01 \|.*?\| )\[FR-001\]\(requirements.md#fr-001\)', r'\1[FR-001](requirements.md)', s, count=1, flags=re.M)),
}
for label, (name, mutate) in mutations.items():
    candidate = dict(documents)
    candidate[name] = mutate(candidate[name])
    if not verify(candidate):
        raise SystemExit('FAIL: synthetic defect was not detected: ' + label)
    print('PASS: negative control rejected ' + label)
digest = hashlib.sha256()
for name, content in sorted(documents.items()):
    digest.update(name.encode() + b'\0' + content.encode() + b'\0')
print('Document-set SHA-256:', digest.hexdigest())
