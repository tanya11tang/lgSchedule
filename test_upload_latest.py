import unittest
from upload_latest import obsolete_html, publish, git_blob_sha


class FakeGitHub:
    def __init__(self, conflict=False, unchanged=False):
        self.calls = []
        self.conflict = conflict
        self.unchanged = unchanged
        self.head = 'old'

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET' and '/refs/' in path:
            return {'object': {'sha': self.head}}
        if method == 'GET' and '/commits/' in path:
            return {'tree': {'sha': 'tree'}}
        if method == 'GET' and '/trees/' in path:
            entries = [{'path': 'site/index.html', 'type': 'blob',
                        'sha': git_blob_sha(b'html') if self.unchanged else 'old'}]
            if not self.unchanged:
                entries.append({'path': 'site/old.html', 'type': 'blob', 'sha': 'old'})
            return {'tree': entries}
        if method == 'PATCH':
            if self.conflict:
                raise ValueError('concurrent update')
            self.head = 'new'
            return {}
        return {'sha': 'new'}


class UploadTests(unittest.TestCase):
    def test_cleanup_is_scoped(self):
        entries = [{'path': p, 'type': 'blob'} for p in
                   ['site/old.HTML', 'site/sub/old.html', 'site/index.html',
                    'outside/old.html', 'site/data.json', 'site-other/old.html']]
        self.assertEqual(obsolete_html(entries), ['site/old.HTML', 'site/sub/old.html'])

    def test_one_atomic_commit(self):
        api = FakeGitHub()
        publish(api, 'main', b'html')
        trees = [body for method, path, body in api.calls if method == 'POST' and path == '/git/trees']
        self.assertEqual(len(trees), 1)
        self.assertEqual({e['path'] for e in trees[0]['tree']}, {'site/index.html', 'site/old.html'})
        patches = [body for method, path, body in api.calls if method == 'PATCH']
        self.assertEqual(patches, [{'sha': 'new', 'force': False}])

    def test_unchanged_has_no_mutations(self):
        api = FakeGitHub(unchanged=True)
        publish(api, 'main', b'html')
        self.assertTrue(all(method == 'GET' for method, _, _ in api.calls))

    def test_conflict_does_not_force_push(self):
        api = FakeGitHub(conflict=True)
        with self.assertRaises(ValueError):
            publish(api, 'main', b'html')
        self.assertFalse(api.calls[-1][2]['force'])


if __name__ == '__main__':
    unittest.main()
