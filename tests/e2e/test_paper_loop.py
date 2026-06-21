from __future__ import annotations

import pytest


class TestFullPaperLoop:
    """M7: propose → validate → review → approve → paper-trade → monitor."""

    @pytest.mark.skip(reason="M7: implement end-to-end paper loop")
    def test_full_paper_loop(self):
        pass

    @pytest.mark.skip(reason="M7: implement with notifications")
    def test_critical_event_fires_notification(self):
        pass

    @pytest.mark.skip(reason="M7: implement with assistant")
    def test_assistant_stages_risk_increasing(self):
        pass

    @pytest.mark.skip(reason="M7: implement with audit log")
    def test_audit_log_captures_all(self):
        pass
