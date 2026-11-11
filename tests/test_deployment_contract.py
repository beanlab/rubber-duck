"""Offline checks for pairing retained Docker images and production configs."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "aws/scripts/deploy-container.sh").read_text()


class DeploymentContractTests(unittest.TestCase):
    def preflight(self, revision_matches=True, config_exists=True):
        # Execute the actual preflight code with fake AWS/Docker functions. No
        # credentials, root access, container daemon, or instance files required.
        config = SCRIPT.split('[[ $CONFIG_BASE_URI ==', 1)[1].split(
            '\nCONTAINER_NAME=', 1
        )[0]
        preflight = SCRIPT.split('docker pull "$IMAGE_URI"', 1)[1].split(
            '\n[[ -f $DATABASE_PATH ]]', 1
        )[0]
        sha = "a" * 40
        program = '''set -Eeuo pipefail
COMMIT_SHA=$SHA
ENVIRONMENT=production
CONFIG_BASE_URI=s3://rubber-duck-config/environments/production/config.yaml
AWS_REGION=us-west-2
IMAGE_URI=example@sha256:example
docker() { printf '%s\\n' "$REVISION"; }
aws() { printf '%s\\n' "$*"; [[ $CONFIG_EXISTS == yes ]]; }
'''
        program += '[[ $CONFIG_BASE_URI ==' + config + preflight
        program += '\nprintf "preflight-complete config=%s\\n" "$CONFIG_URI"\n'
        return subprocess.run(
            ["bash", "-c", program], text=True, capture_output=True,
            env={**os.environ, "SHA": sha,
                 "REVISION": sha if revision_matches else "b" * 40,
                 "CONFIG_EXISTS": "yes" if config_exists else "no"},
        )

    def test_matching_pair(self):
        result = self.preflight()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("production-config-" + "a" * 40 + ".yaml", result.stdout)
        self.assertIn("preflight-complete", result.stdout)

    def test_wrong_image_revision_fails_before_config_lookup(self):
        result = self.preflight(revision_matches=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("image revision does not match", result.stderr)
        self.assertNotIn("head-object", result.stdout)

    def test_missing_config_fails_preflight(self):
        result = self.preflight(config_exists=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("preflight-complete", result.stdout)

    def test_checks_precede_container_stop(self):
        self.assertLess(SCRIPT.index("aws s3api head-object"),
                        SCRIPT.index('docker stop "$CONTAINER_NAME"'))

    def test_workflow_uploads_matching_committed_config(self):
        workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text()
        self.assertIn('production-config-$GITHUB_SHA.yaml', workflow)
        self.assertIn('aws s3 cp production-config.yaml "$CONFIGURATION_URI"', workflow)
        self.assertLess(workflow.index("Upload matching configuration"),
                        workflow.index("  provision:"))


if __name__ == "__main__":
    unittest.main()
