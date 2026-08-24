"""workbench.cli: command PARSING and text FORMATTING only -- every
number printed below is read directly off a domain object `workbench.
interaction.WorkbenchState` returned; this module computes nothing
(requirement 3). Deliberately separated from `workbench.interaction`
(requirement 10) so `dispatch()` can be called directly by tests with no
stdin/stdout involved -- `run_repl()` is the only function here that
actually touches a terminal.

No CLI framework, no third-party dependency: `parse_command`/`dispatch`/
`run_repl` are plain functions over `str`/`WorkbenchState`, using only
the standard library (`sys`, `builtins.input`/`print`).
"""

from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from workbench.interaction import WorkbenchState, bootstrap_default_scenario

HELP_TEXT = """\
Available commands:
  help                 show this text
  status                current session state and selected candidate
  candidates            list every generated ActionCandidate
  select <n>             select candidate n (see `candidates`) for predict/explore/observe
  predict                current model prediction for the selected candidate
  explore <value>        inspect a HYPOTHETICAL outcome -- never advances the session
  observe <value> [unit] record an externally supplied experimental observation; advances the session
  history                the full transition history for the selected candidate
  quit / exit            leave the workbench"""


def _short(identifier: str) -> str:
    """Display-only truncation of a content-hash id -- never used for
    comparison or persisted anywhere; the full id remains available on
    every underlying object."""
    return identifier if len(identifier) <= 16 else identifier[:12] + "..."


def _fmt_optional(value: Optional[float]) -> str:
    return "undetermined" if value is None else str(value)


def parse_command(line: str) -> Tuple[str, List[str]]:
    """Tokenizes one line of input -- `str.split()`, nothing more."""
    tokens = line.strip().split()
    if not tokens:
        return "", []
    return tokens[0].lower(), tokens[1:]


def _format_candidate(index: int, candidate) -> str:
    return (
        f"  [{index}] {_short(candidate.id)}  formulation={candidate.formulation.natural_key}  "
        f"property={candidate.property}  action_class={candidate.action_class}  "
        f"target_context={dict(candidate.target_context)}"
    )


def _cmd_status(state: WorkbenchState) -> str:
    lines = [
        f"Session state: {_short(state.session.state.id)}",
        f"State history length: {len(state.session.state_history)}",
    ]
    if state.selected_candidate is None:
        lines.append("Selected candidate: none -- use `candidates` then `select <n>`")
    else:
        candidate = state.selected_candidate
        prediction = state.session.predict(candidate)
        lines.append(
            f"Selected candidate: {_short(candidate.id)} "
            f"(formulation={candidate.formulation.natural_key}, property={candidate.property})"
        )
        lines.append(
            f"  current prediction: predicted_value={_fmt_optional(prediction.predicted_value)} "
            f"uncertainty={_fmt_optional(prediction.uncertainty)} sample_count={prediction.sample_count}"
        )
    return "\n".join(lines)


def _cmd_candidates(state: WorkbenchState) -> str:
    candidates = state.list_candidates()
    if not candidates:
        return "No candidates were generated for this scenario."
    lines = [f"{len(candidates)} candidate(s):"]
    lines.extend(_format_candidate(i, c) for i, c in enumerate(candidates))
    return "\n".join(lines)


def _cmd_select(state: WorkbenchState, args: List[str]) -> str:
    if len(args) != 1:
        return "usage: select <n>  (see `candidates` for valid indices)"
    try:
        index = int(args[0])
    except ValueError:
        return f"'{args[0]}' is not a valid candidate index -- see `candidates`"
    try:
        candidate = state.select_candidate(index)
    except IndexError as e:
        return str(e)
    return f"Selected candidate {_short(candidate.id)} (property={candidate.property})"


def _cmd_predict(state: WorkbenchState) -> str:
    try:
        prediction = state.predict()
    except ValueError as e:
        return str(e)
    return (
        f"Prediction for candidate {_short(prediction.candidate_id)}\n"
        f"  state: {_short(prediction.state_id)}\n"
        f"  predicted_value: {_fmt_optional(prediction.predicted_value)}\n"
        f"  uncertainty: {_fmt_optional(prediction.uncertainty)}\n"
        f"  sample_count: {prediction.sample_count}"
    )


def _cmd_explore(state: WorkbenchState, args: List[str]) -> str:
    if len(args) != 1:
        return "usage: explore <value>"
    try:
        hypothetical_value = float(args[0])
    except ValueError:
        return f"'{args[0]}' is not a numeric value"
    try:
        outcome = state.explore(hypothetical_value)
    except ValueError as e:
        return str(e)
    return (
        "This is hypothetical. It has NOT been admitted as evidence.\n"
        f"  source state: {_short(outcome.source_state_id)}\n"
        f"  hypothetical value: {outcome.hypothetical_value}\n"
        f"  projected state (hypothetical, never advances the session): {_short(outcome.projected_state_id)}\n"
        f"  prediction before: predicted_value={_fmt_optional(outcome.delta.from_predicted_value)} "
        f"uncertainty={_fmt_optional(outcome.delta.from_uncertainty)}\n"
        f"  prediction after (hypothetical): predicted_value={_fmt_optional(outcome.delta.to_predicted_value)} "
        f"uncertainty={_fmt_optional(outcome.delta.to_uncertainty)}\n"
        f"  delta_predicted_value: {_fmt_optional(outcome.delta.delta_predicted_value)}\n"
        f"  delta_uncertainty: {_fmt_optional(outcome.delta.delta_uncertainty)}\n"
        f"Session state is unchanged: {_short(state.session.state.id)}"
    )


def _cmd_observe(state: WorkbenchState, args: List[str]) -> str:
    if not (1 <= len(args) <= 2):
        return "usage: observe <value> [unit]"
    try:
        value = float(args[0])
    except ValueError:
        return f"'{args[0]}' is not a numeric value"
    unit = args[1] if len(args) == 2 else None
    predecessor_state_id = state.session.state.id
    try:
        assessment, prediction = state.observe(value, unit)
    except ValueError as e:
        return str(e)
    return (
        "Recording this value as an externally supplied experimental observation.\n"
        f"  candidate: {_short(assessment.candidate_id)}\n"
        f"  observation: {_short(assessment.observation.id)}\n"
        "\n"
        "Residual assessment (prediction vs. observed -- no interpretation):\n"
        f"  Previous state: {_short(predecessor_state_id)}\n"
        f"  Prediction: {_fmt_optional(prediction.predicted_value)}\n"
        f"  Observed: {assessment.observed_value}\n"
        f"  Residual: {_fmt_optional(assessment.residual)}\n"
        f"  Absolute residual: {_fmt_optional(assessment.absolute_residual)}\n"
        f"  New state: {_short(state.session.state.id)}"
    )


def _cmd_history(state: WorkbenchState) -> str:
    try:
        diagnostic_set = state.history()
    except ValueError as e:
        return str(e)
    if not diagnostic_set.diagnostics:
        return "No transitions yet for the selected candidate -- observe at least one value first."
    lines = [f"Transition history for candidate {_short(diagnostic_set.candidate_id)} " f"({len(diagnostic_set.diagnostics)} transition(s)):"]
    for i, d in enumerate(diagnostic_set.diagnostics, start=1):
        lines.append(f"  [{i}] {_short(d.predecessor_state_id)} -> {_short(d.successor_state_id)}")
        lines.append(
            f"      previous prediction: predicted_value={_fmt_optional(d.previous_prediction.predicted_value)} "
            f"uncertainty={_fmt_optional(d.previous_prediction.uncertainty)}"
        )
        lines.append(
            f"      new prediction:      predicted_value={_fmt_optional(d.new_prediction.predicted_value)} "
            f"uncertainty={_fmt_optional(d.new_prediction.uncertainty)}"
        )
        lines.append(
            f"      delta_predicted_value={_fmt_optional(d.delta_predicted_value)}  "
            f"delta_uncertainty={_fmt_optional(d.delta_uncertainty)}"
        )
        if d.assessment is None:
            lines.append("      no observation recorded for this transition")
        else:
            lines.append(f"      observation_value={d.observation_value}")
            lines.append(
                f"      residual_against_previous_prediction={_fmt_optional(d.residual_against_previous_prediction)}  "
                f"absolute_residual={_fmt_optional(d.absolute_residual)}"
            )
    return "\n".join(lines)


def dispatch(state: WorkbenchState, command: str, args: List[str]) -> str:
    """The full command table. Returns text to display; never prints
    directly, so this function -- and therefore the entire interaction
    surface -- is callable from a test with no stdin/stdout involved."""
    if command in ("", "help"):
        return HELP_TEXT
    if command == "status":
        return _cmd_status(state)
    if command == "candidates":
        return _cmd_candidates(state)
    if command == "select":
        return _cmd_select(state, args)
    if command == "predict":
        return _cmd_predict(state)
    if command == "explore":
        return _cmd_explore(state, args)
    if command == "observe":
        return _cmd_observe(state, args)
    if command == "history":
        return _cmd_history(state)
    if command in ("quit", "exit"):
        return "__QUIT__"
    return f"Unknown command: {command!r} -- type `help` for the command list"


def run_repl(state: Optional[WorkbenchState] = None) -> None:
    """The only function in this package that touches a real terminal.
    `state` defaults to a fresh `bootstrap_default_scenario()` -- there is
    no persistence, so every invocation of `python -m workbench` starts
    the same fixed scenario from nothing (requirement 12)."""
    if state is None:
        state = bootstrap_default_scenario()
    print("Scout Retrieval Agent -- Interactive Experimental Workbench")
    print("Type `help` for commands, `quit` to exit.\n")
    while True:
        try:
            line = input("workbench> ")
        except EOFError:
            print()
            return
        command, args = parse_command(line)
        output = dispatch(state, command, args)
        if output == "__QUIT__":
            print("Goodbye.")
            return
        print(output)


def main(argv: Optional[List[str]] = None) -> int:
    run_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
