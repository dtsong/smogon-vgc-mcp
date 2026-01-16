"""CLI for VGC multi-agent teambuilder."""

from __future__ import annotations

import argparse
import asyncio
import logging
import shlex
import sys

from vgc_agent.core import BudgetExceededError, Event, EventType, HumanFeedback, Phase
from vgc_agent.orchestrator import TeambuilderOrchestrator

logger = logging.getLogger(__name__)

ALLOWED_MCP_EXECUTABLES = {"uv", "python", "python3", "node", "npx"}


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


PHASE_COLORS = {
    Phase.INITIALIZED: Colors.DIM,
    Phase.ARCHITECTING: Colors.BLUE,
    Phase.CALCULATING: Colors.CYAN,
    Phase.CRITIQUING: Colors.YELLOW,
    Phase.REFINING: Colors.MAGENTA,
    Phase.COMPLETE: Colors.GREEN,
    Phase.FAILED: Colors.RED,
}

SEVERITY_COLORS = {
    "minor": Colors.DIM,
    "moderate": Colors.YELLOW,
    "severe": Colors.RED,
    "critical": Colors.RED,
}


def format_phase(phase: Phase) -> str:
    color = PHASE_COLORS.get(phase, Colors.RESET)
    return f"{color}{phase.value.upper()}{Colors.RESET}"


def print_event(event: Event) -> None:
    ts = event.timestamp.strftime("%H:%M:%S")

    if event.type == EventType.SESSION_STARTED:
        print(f"\n{'=' * 60}")
        print(f"{Colors.BOLD}VGC TEAMBUILDER{Colors.RESET}")
        print(f"{'=' * 60}")
        print(f"Requirements: {event.data.get('requirements', '')}\n")

    elif event.type == EventType.PHASE_STARTED:
        agent = event.data.get("agent", "")
        print(f"\n{Colors.BOLD}[{ts}] {format_phase(event.phase)} - {agent} Agent{Colors.RESET}")
        print(f"{'-' * 40}")

    elif event.type == EventType.AGENT_TOOL_CALL:
        tool = event.data.get("tool", "")
        print(f"  {Colors.CYAN}Calling {tool}...{Colors.RESET}")

    elif event.type == EventType.PHASE_COMPLETED:
        summary = event.data.get("result_summary", "")
        print(f"  {Colors.GREEN}Done: {summary}{Colors.RESET}")

    elif event.type == EventType.TEAM_UPDATED:
        print(f"\n  {Colors.BOLD}Team:{Colors.RESET}")
        for p in event.data.get("team_summary", []):
            print(f"    - {p}")

    elif event.type == EventType.WEAKNESS_FOUND:
        sev = event.data.get("severity", "")
        color = SEVERITY_COLORS.get(sev, Colors.RESET)
        weakness = event.data.get("weakness", "")
        print(f"  {color}Warning: {weakness} ({sev}){Colors.RESET}")

    elif event.type == EventType.ITERATION_STARTED:
        iteration = event.data.get("iteration", 1)
        reason = event.data.get("reason", "")
        print(f"\n{'#' * 60}")
        print(f"# ITERATION {iteration}: {reason}")
        print(f"{'#' * 60}")

    elif event.type == EventType.SESSION_COMPLETED:
        print(f"\n{'=' * 60}")
        print(f"{Colors.GREEN}{Colors.BOLD}TEAM COMPLETE{Colors.RESET}")
        print(f"{'=' * 60}\n")
        print(event.data.get("final_team", ""))
        print(f"\n{'=' * 60}")

    elif event.type == EventType.SESSION_FAILED:
        error = event.data.get("error", "")
        print(f"\n{Colors.RED}{Colors.BOLD}FAILED: {error}{Colors.RESET}")

    elif event.type == EventType.TOKEN_USAGE:
        total_in = event.data.get("total_input", 0)
        total_out = event.data.get("total_output", 0)
        cost = event.data.get("cost_usd", 0.0)
        budget = event.data.get("budget")
        token_msg = f"Tokens: {total_in:,} in / {total_out:,} out (~${cost:.2f})"
        print(f"  {Colors.DIM}{token_msg}{Colors.RESET}")
        if budget is not None:
            percent = event.data.get("budget_percent", 0)
            budget_msg = f"{percent:.0f}% of ${budget:.2f} budget used"
            if percent >= 95:
                print(f"  {Colors.RED}{Colors.BOLD}[CRITICAL] {budget_msg}{Colors.RESET}")
            elif percent >= 80:
                print(f"  {Colors.RED}[WARNING] {budget_msg}{Colors.RESET}")
            elif percent >= 50:
                print(f"  {Colors.YELLOW}[INFO] {budget_msg}{Colors.RESET}")

    elif event.type == EventType.HUMAN_INPUT_REQUESTED:
        pass


def get_human_feedback(
    team_summary: list[str],
    weaknesses: list[dict],
    iteration: int,
) -> HumanFeedback:
    print(f"\n{'=' * 60}")
    print(f"{Colors.BOLD}ITERATION {iteration} COMPLETE - Review Required{Colors.RESET}")
    print(f"{'=' * 60}\n")

    print(f"{Colors.BOLD}Team:{Colors.RESET}")
    for p in team_summary:
        print(f"  - {p}")

    if weaknesses:
        print(f"\n{Colors.BOLD}Weaknesses Found:{Colors.RESET}")
        for w in weaknesses:
            sev = w.get("severity", "unknown")
            color = SEVERITY_COLORS.get(sev, Colors.RESET)
            threat = w.get("threat", "Unknown")
            desc = w.get("description", "")
            print(f"  {color}- {threat} ({sev}): {desc}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Options:{Colors.RESET}")
    print("  [1] Iterate - let agents address weaknesses")
    print("  [2] Finalize - accept team and optimize EVs")
    print("  [3] Abort - stop here")
    print("  [4] Guide - provide specific feedback")

    while True:
        try:
            choice = input(f"\n{Colors.CYAN}Choice [1-4]: {Colors.RESET}").strip()
            if choice == "1":
                return HumanFeedback(action="iterate")
            elif choice == "2":
                return HumanFeedback(action="finalize")
            elif choice == "3":
                return HumanFeedback(action="abort")
            elif choice == "4":
                guidance = input(f"{Colors.CYAN}Guidance: {Colors.RESET}").strip()
                return HumanFeedback(action="guide", guidance=guidance)
            else:
                print(f"{Colors.YELLOW}Please enter 1, 2, 3, or 4{Colors.RESET}")
        except EOFError:
            return HumanFeedback(action="abort")


async def run_cli(
    requirements: str,
    mcp_command: list[str],
    verbose: bool = False,
    budget: float | None = None,
    interactive: bool = False,
) -> int:
    orchestrator = TeambuilderOrchestrator(
        mcp_command,
        budget=budget,
        interactive=interactive,
        human_input_callback=get_human_feedback if interactive else None,
    )

    def on_event(event: Event) -> None:
        if verbose or event.type not in (EventType.AGENT_TOOL_CALL, EventType.AGENT_TOOL_RESULT):
            print_event(event)

    try:
        await orchestrator.connect()
        orchestrator.events.add_listener(on_event)
        state = await orchestrator.build_team(requirements)
        return 0 if state.final_team else 1
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Cancelled{Colors.RESET}")
        return 130
    except BudgetExceededError as e:
        msg = f"BUDGET EXCEEDED: ${e.spent:.2f} spent of ${e.budget:.2f} budget"
        print(f"\n{Colors.RED}{Colors.BOLD}{msg}{Colors.RESET}")
        return 1
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        return 1
    finally:
        await orchestrator.disconnect()


def parse_mcp_command(command_str: str) -> list[str]:
    """Parse and validate MCP command string.

    Uses shlex.split() for proper shell parsing and validates executable
    against an allowlist to prevent command injection attacks.
    """
    try:
        cmd = shlex.split(command_str)
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {e}") from e

    if not cmd:
        raise ValueError("MCP command cannot be empty")

    executable = cmd[0]
    if executable not in ALLOWED_MCP_EXECUTABLES:
        allowed = ", ".join(sorted(ALLOWED_MCP_EXECUTABLES))
        raise ValueError(
            f"MCP executable '{executable}' not in allowlist. Allowed executables: {allowed}"
        )

    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(description="Build VGC teams using multi-agent AI")
    parser.add_argument("requirements", help="Team requirements")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show tool calls")
    parser.add_argument(
        "--mcp-command",
        default="uv run smogon-vgc-mcp",
        help="MCP server command",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Maximum budget in USD (e.g., --budget 5.00)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable human-in-the-loop mode for feedback after each iteration",
    )
    args = parser.parse_args()

    try:
        mcp_command = parse_mcp_command(args.mcp_command)
    except ValueError as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)

    sys.exit(
        asyncio.run(
            run_cli(
                args.requirements,
                mcp_command,
                args.verbose,
                args.budget,
                args.interactive,
            )
        )
    )


if __name__ == "__main__":
    main()
