from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_field_trial_launcher_exposes_bounded_operator_commands_without_local_secrets() -> None:
    launcher = ROOT / "scripts" / "mockingbird-field-trial"
    text = launcher.read_text()

    assert "mockingbird-field-trial" in text
    for command in ("start", "stop", "status", "logs", "open-browser"):
        assert command in text
    assert "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH" in text
    assert "data/models/megadetector" not in text
    assert "tmux" in text
    assert "/tmp/mockingbird-field-trial" in text


def test_field_trial_launcher_refuses_to_start_without_its_ignored_configuration() -> None:
    launcher = ROOT / "scripts" / "mockingbird-field-trial"
    text = launcher.read_text()

    assert "field-trial.env" in text
    assert "MegaDetector is not ready" in text
    assert "duplicate" in text.lower()


def test_field_trial_launcher_stop_waits_for_backend_cleanup_and_reports_forced_fallback() -> None:
    launcher = ROOT / "scripts" / "mockingbird-field-trial"
    text = launcher.read_text()

    assert "FIELD_TRIAL_STOP_GRACE_SECONDS" in text
    assert "kill -0" in text
    assert "durable clean shutdown is unconfirmed" in text
    assert "monitoring-policy" not in text
