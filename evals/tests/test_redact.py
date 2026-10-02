"""evals/bin/redact.py scrubs key values and key-shaped tokens in place."""

import os
import subprocess
import sys
from pathlib import Path

REDACT = Path(__file__).resolve().parents[1] / "bin" / "redact.py"


def test_redacts_literal_values_and_key_shapes(tmp_path):
    f = tmp_path / "trial" / "agent" / "trajectory.json"
    f.parent.mkdir(parents=True)
    f.write_text('{"out": "my-org-secret-value sk-ant-api03-' + "A" * 30 + ' sk-proj-' + "b" * 30 + ' sk-learn"}')
    untouched = tmp_path / "clean.txt"
    untouched.write_text("nothing here")
    env = {**os.environ, "OPENAI_API_KEY": "my-org-secret-value"}
    proc = subprocess.run([sys.executable, str(REDACT), str(tmp_path)], env=env, capture_output=True, text=True)
    assert f.read_text() == '{"out": "[REDACTED] [REDACTED] [REDACTED] sk-learn"}'
    assert untouched.read_text() == "nothing here"
    assert "1 file(s)" in proc.stdout and "my-org-secret-value" not in proc.stdout
