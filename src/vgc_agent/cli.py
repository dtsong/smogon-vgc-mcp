"""CLI for VGC multi-agent teambuilder."""

from __future__ import annotations

import argparse
import asyncio
import sys

from vgc_agent.core import Event, EventType, Phase
from vgc_agent.orchestrator import TeambuilderOrchestrator


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


async def run_cli(requirements: str, mcp_command: list[str], verbose: bool = False) -> int:
    orchestrator = TeambuilderOrchestrator(mcp_command)

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
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        return 1
    finally:
        await orchestrator.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build VGC teams using multi-agent AI")
    parser.add_argument("requirements", help="Team requirements")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show tool calls")
    parser.add_argument(
        "--mcp-command",
        default="uv run smogon-vgc-mcp",
        help="MCP server command",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run_cli(args.requirements, args.mcp_command.split(), args.verbose)))


if __name__ == "__main__":
    main()
