import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text()
JS = (ROOT / "static" / "app.js").read_text()


class FrontendWorkflowContract(unittest.TestCase):
    def test_workspace_keeps_map_and_workflow_side_by_side(self):
        self.assertIn('class="split"', HTML)
        self.assertIn('id="nta-map"', HTML)
        self.assertIn('class="work-panel"', HTML)

    def test_workspace_exposes_reset_event_and_followup_controls(self):
        for required in ('id="reset"', 'id="event-toggle"', 'data-view="tasks"'):
            self.assertIn(required, HTML)

    def test_client_workflow_is_persisted_locally(self):
        self.assertRegex(JS, r"localStorage\.(getItem|setItem)")
        self.assertIn("Claim client", JS)
        self.assertIn("saveOutcome", JS)
        self.assertIn("renderTasks", JS)

    def test_ai_call_card_remains_connected(self):
        self.assertIn("/api/callcard/", JS)
        self.assertIn("Generate AI call brief", JS)

    def test_team_filter_is_a_real_select(self):
        self.assertIn('id="team-filter"', HTML)
        self.assertIn('<select id="team-filter"', HTML)


if __name__ == "__main__":
    unittest.main()
