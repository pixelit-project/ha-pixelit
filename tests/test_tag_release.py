"""Exercise automatic metadata commits and atomic ref updates in local Git repos."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TagReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.remote = self.root / 'remote.git'
        self.work = self.root / 'work'
        self.git('init', '--bare', str(self.remote), cwd=self.root)
        self.git('init', '-b', 'main', str(self.work), cwd=self.root)
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        shutil.copytree(ROOT / 'scripts', self.work / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        manifest = self.work / 'custom_components/pixelit/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"version": "2.0.0"}\n')
        self.original = '# Changelog\n\n## Unreleased\n- New\n\n## 2.0.0\n- Old\n'
        (self.work / 'CHANGELOG.md').write_text(self.original)
        self.git('add', '.')
        self.git('commit', '-m', 'Initial')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', 'origin', 'main')

    def git(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd or self.work, check=True,
                              capture_output=True, text=True).stdout.strip()

    def prepare(self, tag, success=True):
        env = dict(os.environ, RELEASE_TAG=tag, DEFAULT_BRANCH='main',
                   GITHUB_OUTPUT=str(self.root / 'output'), RUNNER_TEMP=str(self.root),
                   PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
        result = subprocess.run(['bash', 'scripts/prepare_tag_release.sh'], cwd=self.work,
                                env=env, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def tag(self, tag):
        self.git('tag', '-a', tag, '-m', tag)
        self.git('push', 'origin', tag)

    def test_stable_updates_remote_branch_tag_and_changelog(self):
        self.tag('v2.1.0')
        self.prepare('v2.1.0')
        head = self.git('rev-parse', 'HEAD')
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/heads/main'), head)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/tags/v2.1.0'), head)
        self.assertEqual(json.loads((self.work / 'custom_components/pixelit/manifest.json').read_text())['version'], '2.1.0')
        self.assertIn('## Unreleased\n\n## 2.1.0 — ', (self.work / 'CHANGELOG.md').read_text())
        self.assertIn('prerelease=false', (self.root / 'output').read_text())
        self.assertIn('commit=' + head, (self.root / 'output').read_text())
        self.prepare('v2.1.0')
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)

    def test_beta_preserves_changelog(self):
        self.tag('v2.1.0-beta.1')
        self.prepare('v2.1.0-beta.1')
        self.assertEqual((self.work / 'CHANGELOG.md').read_text(), self.original)
        self.assertIn('prerelease=true', (self.root / 'output').read_text())

    def test_old_tag_does_not_overwrite_new_branch_commits(self):
        self.tag('v2.1.0')
        self.git('commit', '--allow-empty', '-m', 'Newer work')
        self.git('push', 'origin', 'main')
        head = self.git('rev-parse', 'HEAD')
        self.prepare('v2.1.0', success=False)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/heads/main'), head)

    def test_rejected_push_updates_neither_ref(self):
        self.tag('v2.1.0')
        old_tag = self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/tags/v2.1.0')
        old_branch = self.git('rev-parse', 'HEAD')
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        self.prepare('v2.1.0', success=False)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/heads/main'), old_branch)
        self.assertEqual(self.git('--git-dir=' + str(self.remote), 'rev-parse', 'refs/tags/v2.1.0'), old_tag)
