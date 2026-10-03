"""`harbor analyze`, with the judge's container image set explicitly.

Harbor 0.22 runs the judge in its analyze task template, whose task.toml pins
`docker_image = "python:3.13-slim"`, and installs Claude Code into it (apt-get
+ npm) before every judgement. Nothing in its CLI or job config overrides that
image, so this wrapper points the template at a private copy whose task.toml
names JUDGE_IMAGE (lightcone-eval-base: python:3.13-slim plus the agent CLIs,
so Harbor skips the install), then runs the normal CLI. No Docker tag is
touched. Run it with Harbor's own interpreter:

    <harbor python> evals/bin/judge_analyze.py analyze <args...>
"""

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import harbor.analyze.analyzer as analyzer
from harbor.cli.main import app

image = os.environ.get("JUDGE_IMAGE", "")
if image:
    tmp = Path(tempfile.mkdtemp(prefix="judge-template-")) / "analyze-task-template"
    shutil.copytree(analyzer.ANALYZE_TASK_TEMPLATE_DIR, tmp)
    toml = tmp / "task.toml"
    text, n = re.subn(r'^docker_image\s*=\s*".*"$', f'docker_image = "{image}"', toml.read_text(), flags=re.M)
    if n != 1:
        sys.exit("judge_analyze.py: the analyze template no longer pins docker_image; update this wrapper")
    toml.write_text(text)
    analyzer.ANALYZE_TASK_TEMPLATE_DIR = tmp

sys.argv = ["harbor", *sys.argv[1:]]
app()
