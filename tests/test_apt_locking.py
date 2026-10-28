"""Exercise standalone APT helpers with fake commands, never the host APT."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [ROOT / 'aws/scripts/instance-bootstrap.sh', ROOT / 'aws/scripts/update-host.sh']


def helper(path):
    return 'apt_get() {' + path.read_text().split('apt_get() {', 1)[1].split('\n}', 1)[0] + '\n}\n'


class AptLockTests(unittest.TestCase):
    def invoke(self, script, message, timeout=30, repeat=False):
        scratch = ROOT / '.agents/scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory)
            fake = path / 'apt-get'
            fake.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [[ ! -f "$ATTEMPT" || "$REPEAT" == yes ]]; then
  touch "$ATTEMPT"
  printf '%s\\n' "$MESSAGE" >&2
  exit 100
fi
echo installed
''')
            fake.chmod(0o700)
            # Skip retry sleeps except in the real one-second deadline test.
            program = 'set -Eeuo pipefail\n' + helper(script)
            if timeout != 1:
                program += 'sleep() { :; }\n'
            program += 'apt_get update\n'
            result = subprocess.run(['bash', '-c', program], capture_output=True, text=True,
                                    timeout=10, env={**os.environ,
                                    'PATH': str(path) + ':' + os.environ['PATH'],
                                    'CALLS': str(path / 'calls'), 'ATTEMPT': str(path / 'attempt'),
                                    'MESSAGE': message, 'APT_LOCK_TIMEOUT': str(timeout),
                                    'REPEAT': 'yes' if repeat else 'no'})
            calls = (path / 'calls').read_text().splitlines()
            return result, calls

    def test_helpers_identical(self):
        self.assertEqual(helper(SCRIPTS[0]), helper(SCRIPTS[1]))

    def test_lock_retries(self):
        messages = [
            'E: Could not get lock /var/lib/dpkg/lock-frontend. It is held by process 123 (apt-get)\nE: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), is another process using it?',
            'E: Could not get lock /var/lib/dpkg/lock. It is held by process 123',
            'E: Could not get lock /var/lib/apt/lists/lock. It is held by process 123\nE: Unable to lock directory /var/lib/apt/lists/',
            'E: Could not get lock /var/cache/apt/archives/lock. It is held by process 123\nE: Unable to lock directory /var/cache/apt/archives/',
        ]
        for script in SCRIPTS:
            for message in messages:
                with self.subTest(script=script.name, message=message):
                    result, calls = self.invoke(script, message)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(len(calls), 2)
                    self.assertIn('DPkg::Lock::Timeout=', calls[0])
                    self.assertIn('installed', result.stdout)

    def test_real_errors_not_retried(self):
        for script in SCRIPTS:
            for message in ['E: Unable to locate package nonexistent',
                            'E: Could not get lock /var/lib/apt/lists/lock. It is held by process 123\nE: Real repository failure',
                            'E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)']:
                with self.subTest(script=script.name, message=message):
                    result, calls = self.invoke(script, message)
                    self.assertEqual(result.returncode, 100)
                    self.assertEqual(len(calls), 1)

    def test_deadline_stops_retries(self):
        for script in SCRIPTS:
            result, calls = self.invoke(script, 'E: Could not get lock /var/lib/apt/lists/lock. It is held by process 123', timeout=1, repeat=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(len(calls), 1)
            self.assertIn('timed out waiting for APT locks', result.stderr)


if __name__ == '__main__':
    unittest.main()
