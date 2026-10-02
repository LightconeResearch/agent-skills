"""Harbor's claude-code agent with whole Claude Code plugins loaded via --plugin-dir.

Harbor's `--skill` copies bare skill directories into $CLAUDE_CONFIG_DIR/skills,
which drops everything else a plugin ships (hooks above all). This agent uploads
each plugin directory into the environment and passes it to `claude --plugin-dir`,
so a trial sees the plugin exactly as `claude plugin install` would deliver it:
skills, hooks and their scripts, with ${CLAUDE_PLUGIN_ROOT} set by Claude Code.

    PYTHONPATH=scripts harbor run -a plugin_agent:ClaudeCodePlugin \
        --ak plugin_dirs=/abs/path/plugins/lightcone[,/abs/path/other] ...
"""

from __future__ import annotations

import shlex
from pathlib import Path, PurePosixPath

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

REMOTE_PLUGINS_ROOT = PurePosixPath("/harbor/plugins")


class ClaudeCodePlugin(ClaudeCode):
    def __init__(self, *args, plugin_dirs: str | list[str] = "", **kwargs):
        if isinstance(plugin_dirs, str):
            plugin_dirs = [p for p in plugin_dirs.split(",") if p]
        self.plugin_dirs = [Path(p).expanduser().resolve() for p in plugin_dirs]
        for plugin in self.plugin_dirs:
            if not (plugin / ".claude-plugin" / "plugin.json").is_file():
                raise ValueError(f"{plugin} has no .claude-plugin/plugin.json")
        super().__init__(*args, **kwargs)

    def _remote(self, plugin: Path) -> PurePosixPath:
        return REMOTE_PLUGINS_ROOT / plugin.name

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        plugin_flags = " ".join(
            f"--plugin-dir {shlex.quote(self._remote(p).as_posix())}"
            for p in self.plugin_dirs
        )
        return " ".join(f for f in (flags, plugin_flags) if f)

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        for plugin in self.plugin_dirs:
            remote = self._remote(plugin).as_posix()
            await self.exec_as_root(environment, f"mkdir -p {shlex.quote(remote)}")
            await environment.upload_dir(plugin, remote)
        if self.plugin_dirs:
            await self.exec_as_root(
                environment, f"chmod -R a+rX {REMOTE_PLUGINS_ROOT.as_posix()}"
            )
        await super().run(instruction, environment, context)
