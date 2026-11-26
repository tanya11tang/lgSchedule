"""Upload a validated local HTML and remove old site HTML in one Git commit.

No credentials are written to disk. GitHub token is read from GITHUB_TOKEN.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def read_html(path):
    data = Path(path).read_bytes()
    html = data.decode('utf-8-sig')
    if '<html' not in html.lower() or '</html>' not in html.lower() or '__DATA__' in html:
        raise ValueError('HTML is missing or incomplete; previous version will be preserved')
    if re.search(r'(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})', html):
        raise ValueError('Possible GitHub credential in HTML; upload refused')
    return data


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def obsolete_html(entries):
    # Only HTML files inside the dedicated site/ directory are deleted.
    return [e['path'] for e in entries if e['type'] == 'blob'
            and e['path'].startswith('site/') and e['path'].lower().endswith('.html')
            and e['path'] != 'site/index.html']


class GitHub:
    def __init__(self, repo, token):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Repository must be OWNER/REPO')
        self.base = 'https://api.github.com/repos/' + repo
        self.token = token

    def call(self, method, path, body=None):
        request = Request(self.base + path,
                          data=json.dumps(body).encode() if body is not None else None,
                          method=method,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Accept': 'application/vnd.github+json',
                                   'Content-Type': 'application/json',
                                   'X-GitHub-Api-Version': '2022-11-28',
                                   'User-Agent': 'carousel-uploader'})
        with urlopen(request, timeout=60) as response:
            return json.load(response)


def publish(api, branch, data, bootstrap=False):
    ref_path = '/git/refs/heads/' + quote(branch, safe='')
    # Dedicated repository must be initialized with a README before use.
    head = api.call('GET', ref_path)['object']['sha']
    commit = api.call('GET', '/git/commits/' + head)
    tree = api.call('GET', '/git/trees/' + commit['tree']['sha'] + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Repository tree is too large to safely prune; upload refused')
    entries = tree['tree']
    remove = obsolete_html(entries)
    desired = {'site/index.html': data}
    if bootstrap:
        root = Path(__file__).resolve().parent
        desired['.github/workflows/pages.yml'] = (root / '.github/workflows/pages.yml').read_bytes()
    existing = {e['path']: e['sha'] for e in entries if e['type'] == 'blob'}
    updates = []
    for path, content in desired.items():
        if existing.get(path) == git_blob_sha(content):
            continue
        blob = api.call('POST', '/git/blobs',
                        {'content': base64.b64encode(content).decode(), 'encoding': 'base64'})
        updates.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    updates.extend({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None} for path in remove)
    if not updates:
        print('Already current; no changes needed')
        return
    new_tree = api.call('POST', '/git/trees', {'base_tree': commit['tree']['sha'], 'tree': updates})
    new_commit = api.call('POST', '/git/commits',
                          {'message': 'Update latest carousel and remove old site HTML',
                           'tree': new_tree['sha'], 'parents': [head]})
    # Never force-push. A competing branch update fails safely and requires a rerun.
    api.call('PATCH', ref_path, {'sha': new_commit['sha'], 'force': False})
    verified = api.call('GET', ref_path)['object']['sha']
    if verified != new_commit['sha']:
        raise ValueError('Branch changed after upload; check GitHub before retrying')
    print(f'Uploaded latest HTML; removed {len(remove)} old site HTML file(s)')
    print('Commit: ' + new_commit['sha'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True, help='Validated production HTML, not a candidate')
    parser.add_argument('--repo', default=os.environ.get('CAROUSEL_GITHUB_REPO'))
    parser.add_argument('--branch', default='main')
    parser.add_argument('--bootstrap', action='store_true', help='Also install Pages workflow')
    parser.add_argument('--dry-run', action='store_true', help='Validate locally, without any network access')
    args = parser.parse_args()
    data = read_html(args.file)
    if args.dry_run:
        print(f'Local HTML valid ({len(data)} bytes); no network requests made')
        return
    if not args.repo:
        raise ValueError('Set CAROUSEL_GITHUB_REPO or pass --repo OWNER/REPO')
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('GITHUB_TOKEN is missing; no credentials are saved by this script')
    publish(GitHub(args.repo, token), args.branch, data, args.bootstrap)


if __name__ == '__main__':
    try:
        main()
    except HTTPError as error:
        print(f'GitHub HTTP {error.code}; check repository, token permissions and branch rules', file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
