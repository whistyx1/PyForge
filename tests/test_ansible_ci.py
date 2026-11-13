"""Configuration selection and deploy ordering for the GitHub workflow."""

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "infra/ansible/should_configure.py"
WORKFLOW = ROOT / ".github/workflows/deploy.yml"


class AnsiblePipelineTests(unittest.TestCase):
    def select(self, event, *paths):
        return subprocess.run(
            [sys.executable, str(SELECTOR), event],
            input="\n".join(paths) + "\n",
            text=True,
            capture_output=True,
        )

    def test_ansible_change_selects_configuration(self):
        result = self.select("push", "app/config/health.py", "infra/ansible/site.yml")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "true"))

    def test_app_only_change_skips_configuration(self):
        result = self.select("push", "app/config/health.py", "tests/test_readiness.py")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "false"))

    def test_manual_run_forces_configuration(self):
        result = self.select("workflow_dispatch")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "true"))

    def test_configuration_failure_stops_deploy_and_order_is_preserved(self):
        workflow = WORKFLOW.read_text()
        configure = workflow.index("- name: Configure server with Ansible")
        deploy = workflow.index("- name: Deploy with SSM")
        self.assertLess(configure, deploy)
        configure_step = workflow[configure:workflow.index("- name: Copy GitHub secret", configure)]
        self.assertIn("ansible-playbook", configure_step)
        self.assertNotIn("continue-on-error: true", configure_step)
        self.assertNotIn("|| true", configure_step)
        self.assertIn("if: steps.server_config.outputs.configure == 'true'", configure_step)
        self.assertIn("needs: publish", workflow)

    def test_ssm_inventory_and_transfer_policy_are_separate_from_backups(self):
        inventory = (ROOT / "infra/ansible/inventory.aws_ssm.yml").read_text()
        policy = (ROOT / "infra/terraform/backups.tf").read_text()
        self.assertIn("- instance-id", inventory)
        self.assertIn('prefix = "i-"', policy)
        self.assertIn('"${aws_s3_bucket.backups.arn}/i-*/*"', policy)
        self.assertIn('prefix = "backups/"', policy)
