"""workbench.cli: command PARSING and text FORMATTING only -- every
number printed below is read directly off a domain object `workbench.
interaction.WorkbenchState` (or a `materials.*`/`experiment.*` object it
already produced) returned; this module computes nothing itself.
Deliberately separated from `workbench.interaction` (requirement 10) so
`dispatch()` can be called directly by tests with no stdin/stdout
involved -- `run_repl()` is the only function here that actually touches
a terminal.

No CLI framework, no third-party dependency: `parse_command`/`dispatch`/
`run_repl` are plain functions over `str`/`WorkbenchState`, using only
the standard library (`sys`, `builtins.input`/`print`).

PHASE 70 -- FROM DEMONSTRATION TO INSTRUMENT: `run_repl`'s default
scenario is now `workbench.interaction.bootstrap_multi_candidate_scenario`
(two candidates) rather than the single-candidate `bootstrap_default_
scenario` (still used by `workbench.demo`, unchanged) -- `decide`/
`select <n>` are meaningless with only one candidate to choose among.
Candidate display/selection is 1-INDEXED (`[1]`, `select 1`) here, a
pure presentation choice this module owns: `WorkbenchState.select_
candidate`/`list_candidates` remain plain 0-indexed Python sequence
operations underneath (`_display_index` below is the only place the
translation happens); nothing about `workbench.interaction` changed to
accommodate this. `decide` is deliberately READ-ONLY with respect to
`state.selected_candidate` -- it reports which candidate the existing
`evaluate_utility_set`/`optimize_candidates` composition currently
prefers, but only `select <n>` (a separate, explicit human choice)
establishes which candidate `predict`/`explore`/`observe` act on next,
per this phase's own instruction that a policy recommendation and the
human's interaction choice remain two different things.
"""

from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from materials.candidates import ActionCandidate
from workbench.interaction import WorkbenchState, bootstrap_multi_candidate_scenario, evaluate_decision

HELP_TEXT = """\
Available commands:
  help                    show this text
  status                   current session state, samples, selection, latest residual
  candidates               list every generated ActionCandidate with prediction/utility/optimization
  decide                   evaluate the current decision landscape (evaluate_utility_set + optimize_candidates)
  select <n>                select candidate n (see `candidates`) for predict/explore/observe
  predict                   current model prediction for the selected candidate
  explore <value>           inspect a HYPOTHETICAL outcome -- never advances the session
  observe <value> [unit]    record an externally supplied experimental observation; advances the session
  history                   the full transition history for the selected candidate
  quit / exit               leave the workbench"""


def _short(identifier: str) -> str:
    """Display-only truncation of a content-hash id -- never used for
    comparison or persisted anywhere; the full id remains available on
    every underlying object."""
    return identifier if len(identifier) <= 16 else identifier[:12] + "..."


def _fmt_optional(value: Optional[float]) -> str:
    return "undetermined" if value is None else str(value)


def _fmt_signed(value: Optional[float]) -> str:
    """Same honesty as `_fmt_optional`, plus an explicit '+' for a
    positive value -- the residual's sign is the one piece of
    information this display must never obscure."""
    if value is None:
        return "undetermined"
    return f"+{value}" if value > 0 else str(value)


def _display_index(state: WorkbenchState, candidate: ActionCandidate) -> int:
    """1-indexed display number for `candidate` -- see module docstring
    for why this translation lives here, not in `WorkbenchState`."""
    return state.list_candidates().index(candidate) + 1


def parse_command(line: str) -> Tuple[str, List[str]]:
    """Tokenizes one line of input -- `str.split()`, nothing more."""
    tokens = line.strip().split()
    if not tokens:
        return "", []
    return tokens[0].lower(), tokens[1:]


def _cmd_status(state: WorkbenchState) -> str:
    lines = [
        f"Session state: {_short(state.session.state.id)}",
        f"State history length: {len(state.session.state_history)}",
        f"Real samples (all candidates): {state.total_sample_count()}",
        f"Available candidates: {len(state.list_candidates())}",
    ]
    if state.selected_candidate is None:
        lines.append("Selected candidate: none -- use `candidates` then `select <n>`")
    else:
        candidate = state.selected_candidate
        prediction = state.session.predict(candidate)
        lines.append(
            f"Selected candidate: [{_display_index(state, candidate)}] "
            f"(formulation={candidate.formulation.natural_key}, property={candidate.property}, "
            f"context={dict(candidate.target_context)})"
        )
        lines.append(
            f"  current prediction: predicted_value={_fmt_optional(prediction.predicted_value)} "
            f"uncertainty={_fmt_optional(prediction.uncertainty)} sample_count={prediction.sample_count}"
        )
    if state.assessments:
        latest = state.assessments[-1]
        lines.append(
            f"Latest observation: candidate={_short(latest.candidate_id)}  observed={latest.observed_value}"
        )
        lines.append(f"Latest residual: {_fmt_signed(latest.residual)}")
    else:
        lines.append("Latest observation: none yet")
    if state.last_counterfactual is not None:
        cf = state.last_counterfactual
        lines.append(
            f"Counterfactual currently inspected: hypothetical_value={cf.hypothetical_value} "
            f"(projected state {_short(cf.projected_state_id)} -- hypothetical, not part of real history)"
        )
    else:
        lines.append("Counterfactual currently inspected: none")
    return "\n".join(lines)


def _cmd_candidates(state: WorkbenchState) -> str:
    candidates = state.list_candidates()
    if not candidates:
        return "No candidates were generated for this scenario."
    decision = evaluate_decision(state.candidates, state.session.state, state.session.iteration)
    optimization_by_id = {o.candidate_id: o for o in decision.optimizations}
    lines = [f"{len(candidates)} candidate(s):", ""]
    for i, candidate in enumerate(candidates, start=1):
        prediction = state.session.predict(candidate)
        estimate = state.information_value_estimate(candidate)
        optimization = optimization_by_id[candidate.id]
        lines.append(f"[{i}] formulation={candidate.formulation.natural_key}")
        lines.append(f"    property={candidate.property}")
        lines.append(f"    context={dict(candidate.target_context)}")
        lines.append(
            f"    prediction={_fmt_optional(prediction.predicted_value)}  "
            f"uncertainty={_fmt_optional(prediction.uncertainty)}"
        )
        lines.append(f"    samples={prediction.sample_count}")
        lines.append(f"    information_value={_fmt_optional(estimate.estimate)} ({estimate.estimate_status})")
        lines.append(
            f"    utility={_fmt_optional(optimization.utility.utility)} ({optimization.utility.utility_status})  "
            f"optimization={optimization.status}"
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def _cmd_decide(state: WorkbenchState) -> str:
    optimization = state.decide()
    selected = [o for o in optimization.optimizations if o.status == "SELECTED"]
    lines = ["Decision", "--------"]
    if not selected:
        lines.append("No candidate could be selected under the current policy (see `candidates` for why).")
    else:
        chosen = selected[0]
        candidate = next(c for c in state.list_candidates() if c.id == chosen.candidate_id)
        lines.append(f"Selected candidate: [{_display_index(state, candidate)}]")
        lines.append("Reason:")
        lines.append(f"  utility = {_fmt_optional(chosen.utility.utility)} ({chosen.utility.utility_status})")
        lines.append(f"  policy  = max_candidates={optimization.policy.max_candidates}")
    lines.append("")
    lines.append(
        "This is a policy-selected recommendation, not an autonomous action -- "
        "use `select <n>` to actually establish a candidate to act on."
    )
    lines.append("")
    lines.append("Full candidate landscape:")
    for o in optimization.optimizations:
        candidate = next(c for c in state.list_candidates() if c.id == o.candidate_id)
        lines.append(
            f"  [{_display_index(state, candidate)}] utility={_fmt_optional(o.utility.utility)} "
            f"({o.utility.utility_status})  status={o.status}"
        )
    return "\n".join(lines)


def _cmd_select(state: WorkbenchState, args: List[str]) -> str:
    if len(args) != 1:
        return "usage: select <n>  (see `candidates` for valid numbers)"
    try:
        n = int(args[0])
    except ValueError:
        return f"'{args[0]}' is not a valid candidate number -- see `candidates`"
    try:
        candidate = state.select_candidate(n - 1)
    except IndexError:
        return (
            f"candidate number {n} is out of range -- see `candidates` for valid numbers "
            f"(1..{len(state.list_candidates())})"
        )
    return f"Selected candidate [{n}] (property={candidate.property}, context={dict(candidate.target_context)})"


def _cmd_predict(state: WorkbenchState) -> str:
    try:
        prediction = state.predict()
    except ValueError as e:
        return str(e)
    return (
        f"Prediction for candidate [{_display_index(state, state.selected_candidate)}]\n"  # type: ignore[arg-type]
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
    pre_state_id = state.session.state.id
    try:
        outcome = state.explore(hypothetical_value)
    except ValueError as e:
        return str(e)
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed: state.explore() above only succeeds once one is selected
    estimate_after = state.information_value_estimate(candidate, outcome.projected_state)
    return (
        "Counterfactual\n"
        "--------------\n"
        f"candidate: [{_display_index(state, candidate)}]\n"
        f"hypothetical value: {outcome.hypothetical_value}\n"
        "\n"
        f"projected state: {_short(outcome.projected_state_id)}\n"
        f"prediction after: {_fmt_optional(outcome.delta.to_predicted_value)}\n"
        f"delta: predicted_value={_fmt_optional(outcome.delta.delta_predicted_value)}  "
        f"uncertainty={_fmt_optional(outcome.delta.delta_uncertainty)}\n"
        f"information value after (hypothetical): {_fmt_optional(estimate_after.estimate)} "
        f"({estimate_after.estimate_status})\n"
        "evidence admitted: NO\n"
        f"real session changed: {'YES' if state.session.state.id != pre_state_id else 'NO'}\n"
        "\n"
        "This is hypothetical. It has NOT been admitted as evidence."
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
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed: state.observe() above only succeeds once one is selected
    samples_for_candidate = state.session.predict(candidate).sample_count
    observed_unit = assessment.result.content.get("unit", "")
    return (
        "Observation accepted -- this value is an externally supplied experimental observation\n"
        "------------------------------------------------------------------------------------\n"
        f"candidate: [{_display_index(state, candidate)}]\n"
        f"observed: {assessment.observed_value} {observed_unit}\n"
        "\n"
        f"prediction before observation: {_fmt_optional(prediction.predicted_value)}\n"
        f"residual: {_fmt_signed(assessment.residual)}\n"
        f"absolute residual: {_fmt_optional(assessment.absolute_residual)}\n"
        "\n"
        "state:\n"
        f"  previous = {_short(predecessor_state_id)}\n"
        f"  current  = {_short(state.session.state.id)}\n"
        "\n"
        f"samples for candidate: {samples_for_candidate}"
    )


def _cmd_history(state: WorkbenchState) -> str:
    try:
        diagnostic_set = state.history()
    except ValueError as e:
        return str(e)
    if not diagnostic_set.diagnostics:
        return "No transitions yet for the selected candidate -- observe at least one value first."
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed: state.history() above only succeeds once one is selected
    lines = [
        f"Transition history for candidate [{_display_index(state, candidate)}] "
        f"({len(diagnostic_set.diagnostics)} transition(s)):"
    ]
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
                f"      residual_against_previous_prediction={_fmt_signed(d.residual_against_previous_prediction)}  "
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
    if command == "decide":
        return _cmd_decide(state)
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
    `state` defaults to a fresh `bootstrap_multi_candidate_scenario()`
    (Phase 70) -- there is no persistence, so every invocation of
    `python -m workbench` starts the same fixed, two-candidate scenario
    from nothing, immediately usable with `decide`/`select <n>` needing
    no external file."""
    if state is None:
        state = bootstrap_multi_candidate_scenario()
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
