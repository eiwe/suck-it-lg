from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCANNER = Path(__file__).resolve().parents[1] / 'scripts/check-staged-secrets.py'


class StagedSecretTests(unittest.TestCase):
    def scan(self, name, content):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            subprocess.run(['git', '-C', directory, 'add', '--', name], check=True)
            return subprocess.run([sys.executable, str(SCANNER)], cwd=directory,
                                  capture_output=True, text=True)

    def test_normal_documentation_passes(self):
        result = self.scan('README.md', 'Run a script on your own TV.\n')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_private_path_rejected_even_without_recognized_secret(self):
        result = self.scan('.private/config.json', '{}')
        self.assertNotEqual(result.returncode, 0)

    def test_private_key_and_token_are_rejected_without_echoing_values(self):
        samples = ['-----BEGIN ' + 'OPENSSH ' + 'PRIVATE KEY-----', 'ghp_' + 'A' * 36]
        for sample in samples:
            with self.subTest(sample_type=sample.split(' ')[0]):
                result = self.scan('accident.txt', sample)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(sample, result.stdout)


if __name__ == '__main__':
    unittest.main()
