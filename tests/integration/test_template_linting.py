# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pathlib
import subprocess
from datetime import datetime

from rich.console import Console

from src.cli.utils.template import get_available_agents, get_deployment_targets

console = Console()
TARGET_DIR = "target"


def run_command(
    cmd: list[str], cwd: pathlib.Path | None, message: str
) -> subprocess.CompletedProcess[bytes]:
    """Helper function to run commands and handle output"""
    console.print(f"\n[bold blue]{message}...[/]")

    # For mypy, we want to see the output even if it fails
    is_mypy = cmd[2] == "mypy"

    if is_mypy:
        # For mypy, run without capturing output to preserve formatting
        mypy_result = subprocess.run(
            cmd,
            check=False,  # Don't check return code for mypy
            cwd=cwd,
        )

        if mypy_result.returncode != 0:
            console.print(
                f"[bold red]Mypy failed with exit code: {mypy_result.returncode}[/]"
            )
            raise subprocess.CalledProcessError(mypy_result.returncode, cmd, None, None)
        return mypy_result
    else:
        # For other commands, use capture_output
        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=False, cwd=cwd
            )

            console.print(f"[green]✓[/] {message} completed successfully")
            if result.stdout:
                console.print(result.stdout.decode())

            return result

        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Error: {message}[/]")
            if e.stdout:
                console.print(e.stdout.decode())
            if e.stderr:
                console.print(e.stderr.decode())
            console.print(f"[bold red]Exit code: {e.returncode}[/]")
            raise


def test_template_linting(agent: str, deployment_target: str) -> None:
    """Test linting for a specific agent template"""
    project_name = f"lint_test_{agent}_{deployment_target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    project_path = pathlib.Path(TARGET_DIR) / project_name

    try:
        # Create target directory if it doesn't exist
        os.makedirs(TARGET_DIR, exist_ok=True)

        # Template the project
        run_command(
            [
                "python",
                "-m",
                "src.cli.main",
                "create",
                project_name,
                "--agent",
                agent,
                "--deployment-target",
                deployment_target,
                "--auto-approve",
            ],
            pathlib.Path(TARGET_DIR),
            f"Templating {agent} project with {deployment_target}",
        )

        # Install dependencies
        run_command(
            [
                "uv",
                "sync",
                "--dev",
                "--extra",
                "streamlit",
                "--extra",
                "jupyter",
                "--extra",
                "lint",
                "--frozen",
            ],
            project_path,
            "Installing dependencies",
        )

        # Run linting commands one by one
        lint_commands = [
            ["uv", "run", "codespell"],
            ["uv", "run", "ruff", "check", ".", "--diff"],
            ["uv", "run", "ruff", "format", ".", "--check", "--diff"],
            ["uv", "run", "mypy", "."],
        ]

        for cmd in lint_commands:
            try:
                command_name = cmd[2]
                command_args = cmd[3] if len(cmd) > 3 else ""
                run_command(cmd, project_path, f"Running {command_name} {command_args}")
            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]Linting failed on {cmd[2]}[/]")
                if e.stdout:
                    console.print(e.stdout)
                if e.stderr:
                    console.print(e.stderr)
                raise

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e!s}")
        raise


def get_test_combinations() -> list[tuple[str, str]]:
    """Generate all valid agent and deployment target combinations for testing."""
    combinations = []
    agents = get_available_agents()

    for agent_info in agents.values():
        agent_name = agent_info["name"]
        # Get available deployment targets for this agent
        targets = get_deployment_targets(agent_name)

        # Add each valid combination
        for target in targets:
            combinations.append((agent_name, target))

    return combinations


def get_test_combinations_to_run() -> list[tuple[str, str]]:
    """Get the test combinations to run, either from environment or all available."""
    if os.environ.get("_TEST_AGENT_COMBINATION"):
        env_combo_parts = os.environ.get("_TEST_AGENT_COMBINATION", "").split(",")
        if len(env_combo_parts) == 2:
            env_combo = (env_combo_parts[0], env_combo_parts[1])
            console.print(
                f"[bold blue]Running test for combination from environment:[/] {env_combo}"
            )
            return [env_combo]
        else:
            console.print(
                f"[bold red]Invalid environment combination format:[/] {env_combo_parts}"
            )

    combos = get_test_combinations()
    console.print(f"[bold blue]Running tests for all combinations:[/] {combos}")
    return combos


def test_all_templates() -> None:
    """Test linting for all template combinations"""
    combinations = get_test_combinations_to_run()

    for agent, deployment_target in combinations:
        console.print(f"\n[bold cyan]Testing {agent} with {deployment_target}[/]")
        test_template_linting(agent, deployment_target)


if __name__ == "__main__":
    test_all_templates()
