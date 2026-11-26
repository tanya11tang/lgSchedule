"""Install carousel workflow using an ephemeral GitHub token, without saving it."""
import getpass
import os
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from upload_latest import GitHub, git_blob_sha


def setup(api):
    repo = api.call('GET', '')
    if not repo.get('permissions', {}).get('push'):
        raise ValueError('Token does not have write access to this repository')
    if repo['default_branch'] != 'main':
        raise ValueError('Workflow expects the default branch to be main')
    ref = '/git/refs/heads/main'
    head = api.call('GET', ref)['object']['sha']
    commit = api.call('GET', '/git/commits/' + head)
    tree = api.call('GET', '/git/trees/' + commit['tree']['sha'] + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Repository tree is truncated; setup refused')
    existing = {entry['path']: entry['sha'] for entry in tree['tree']}
    root = Path(__file__).resolve().parent
    files = ['.github/workflows/pages.yml', 'upload_latest.py',
             'test_upload_latest.py', 'DEPLOYMENT.md', 'setup_github.py']
    changes = []
    for path in files:
        data = (root / path).read_bytes()
        if existing.get(path) == git_blob_sha(data):
            continue
        import base64
        blob = api.call('POST', '/git/blobs',
                        {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})
        changes.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    if changes:
        new_tree = api.call('POST', '/git/trees',
                            {'base_tree': commit['tree']['sha'], 'tree': changes})
        new_commit = api.call('POST', '/git/commits',
                              {'message': 'Install carousel upload and Pages workflow',
                               'tree': new_tree['sha'], 'parents': [head],
                               'author': {'name': 'Carousel Automation',
                                          'email': 'carousel-automation@users.noreply.github.com'}})
        api.call('PATCH', ref, {'sha': new_commit['sha'], 'force': False})
        print('Workflow installed.')
    else:
        print('Workflow already installed.')
    try:
        page = api.call('GET', '/pages')
    except HTTPError as error:
        if error.code != 404:
            raise
        page = api.call('POST', '/pages', {'build_type': 'workflow'})
    else:
        if page.get('build_type') != 'workflow':
            page = api.call('PUT', '/pages', {'build_type': 'workflow'})
    print('GitHub Pages configured for GitHub Actions.')
    print('The page becomes available after the first validated production HTML is uploaded.')
    print('Token was not saved. Unattended daily uploads will need a separately configured secret.')


if __name__ == '__main__':
    token = None
    api = None
    try:
        token = os.environ.get('GITHUB_TOKEN') or getpass.getpass('GitHub token (hidden, used for this process only): ')
        if not token.strip():
            raise ValueError('No token entered')
        api = GitHub('tanya11tang/lgSchedule', token.strip())
        setup(api)
    except HTTPError as error:
        print(f'GitHub HTTP {error.code}: check Contents, Workflows and Pages write permissions.', file=sys.stderr)
        print('Failed endpoint: ' + error.url, file=sys.stderr)
        try:
            details = json.load(error)
            print('GitHub reason: ' + str(details.get('message', 'No details')), file=sys.stderr)
        except (ValueError, OSError):
            pass
        sys.exit(1)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    finally:
        if api is not None:
            api.token = ''
        token = None
