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

PHASE 73 -- `main` optionally accepts `--scenario <path.json>`: the
smallest natural extension over `run_repl`'s pre-existing `state`
parameter (investigated, not assumed -- see `workbench/interaction.py`'s
own Phase 73 docstring section for why no new scenario TYPE was
needed). With no `--scenario` argument, `main`/`run_repl` behave exactly
as before (`bootstrap_multi_candidate_scenario`, unchanged) -- the
default two-candidate startup is byte-for-byte compatible.

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

PHASE 71 -- INVESTIGATION FINDINGS (re-read fresh, not assumed from any
prior phase report, per this phase's own instruction):

  1. SESSION USABILITY: `WorkbenchState` (Phase 68/70) already holds
     everything a repeated interaction needs -- `selected_candidate`,
     `assessments`, `last_counterfactual`, `last_decision` -- with no
     mutable SCIENTIFIC state anywhere (every field either names an
     immutable domain object or is plain interaction bookkeeping, per
     that module's own docstring). No new presentation-level state was
     missing; nothing was added to `workbench/interaction.py` this
     phase.

  2. DECISION VISIBILITY: candidate identity/context/prediction/
     uncertainty/sample count/information-value status/utility/
     optimization status were already all exposed by `candidates`/
     `decide` (Phase 70). This phase adds the candidate's own `id` and
     the shared `process` (read from `state.session.iteration.query.
     process_natural_key` -- a real field, not fabricated) to the
     candidate listing, since Phase 70's version omitted them.

  3. OBSERVATION SEMANTICS: `WorkbenchState.observe` was already, and
     remains, a thin wrapper around the real admission path (`admit_
     record`/`admit_experimental_result`/`ExperimentSession.observe`) --
     it never fabricates an `Observation`. No `experiment.interface.
     ActionDispatcher` seam is needed here: that Protocol exists for
     AUTOMATED dispatch (`experiment.step.run_experiment_step`); this
     CLI's `observe <value>` is the human supplying an externally
     obtained result directly, so there is no "dispatch" step to seam --
     inventing one would add lab-automation machinery this phase
     explicitly forbids, to stand in for a human who is already right
     here typing the number.

  4. COUNTERFACTUAL SEMANTICS: `explore <value>` already communicated
     every required fact (Phase 70) -- hypothetical, not evidence,
     source state unchanged, projected state identity, prediction after.
     This phase only adjusts wording/section headers to match this
     phase's own illustrative transcript more closely; the underlying
     `WorkbenchState.explore`/`session.inspect_counterfactual` call is
     unchanged.

  5. HISTORY: `history` (Phase 70) already exposes state_before/
     candidate/predicted_value_before/observed_value/signed_residual/
     state_after per transition, via `materials.diagnostics.
     StateTransitionDiagnostic` fields -- no second history model exists
     or was added.

  6. DIAGNOSTICS: `materials.diagnostics.diagnose_transitions` already
     computes everything a "diagnostics" view would show (Phase 57) --
     `WorkbenchState.history()` already calls it. The one genuine gap
     this phase's investigation found: nothing exposed it as its OWN
     command with its own framing (`history` mixes narrative and detail
     together). `diagnostics` below is a SECOND presentation over the
     exact same `StateTransitionDiagnosticSet` `history` already
     produces -- `WorkbenchState.history()` is called again, unmodified;
     no new `WorkbenchState` method, no new diagnostic mathematics.

IMPLEMENTATION RULE (this phase's own instruction): every command
handler below is now a thin dispatcher into a named `format_*`
function -- `format_candidate`/`format_prediction`/`format_decision`/
`format_selection`/`format_assessment`/`format_counterfactual`/
`format_transition`/`format_diagnostic` -- each a deterministic,
side-effect-free renderer of an already-existing domain object. None
computes a mean, variance, residual, utility, or information value;
each only reads fields off the object it was given.
"""

from __future__ import annotations

import json
import sys
from typing import List, Mapping, Optional, Tuple

from materials.assessment import PredictionAssessment
from materials.candidates import ActionCandidate
from materials.diagnostics import StateTransitionDiagnostic
from materials.model_state import Prediction
from materials.optimization import CandidateOptimization, OptimizationResult
from workbench.interaction import (
    WorkbenchState, bootstrap_multi_candidate_scenario, bootstrap_research_scenario, evaluate_decision,
)

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
  history                   the transition history for the selected candidate
  diagnostics               the same transitions, in materials.diagnostics' own full detail
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


def _format_context_compact(context: object) -> str:
    """Display-only one-line rendering of an experimental context, for
    the startup banner's candidate roster. A key ending `_c` is shown as
    `<value> C` -- the unit is read from the key the SCENARIO AUTHOR
    wrote, never inferred from the value or invented here; every other
    key renders as a plain `key=value` pair."""
    items = sorted(dict(context).items()) if isinstance(context, Mapping) else []
    if not items:
        return "(no context)"
    parts = [f"{value} C" if key.endswith("_c") else f"{key}={value}" for key, value in items]
    return ", ".join(parts)


def format_scenario_banner(state: WorkbenchState) -> str:
    """The startup roster `run_repl` prints: which study is loaded (when
    a `ResearchScenario` was supplied), every candidate it generated, and
    how many real observations exist so far -- so a researcher can see
    the whole search space before typing anything. Every value is read
    off already-constructed objects; nothing here is computed."""
    lines: List[str] = []
    if state.scenario is not None:
        lines.append("Research scenario:")
        lines.append(f"  {state.scenario.name}")
        lines.append("")
    candidates = state.list_candidates()
    lines.append("Candidates:")
    if not candidates:
        lines.append("  (none generated for this scenario)")
    for i, candidate in enumerate(candidates, start=1):
        lines.append(
            f"  {i}. {candidate.formulation.natural_key} / {candidate.property} / "
            f"{_format_context_compact(candidate.target_context)}"
        )
    lines.append("")
    lines.append("State:")
    lines.append(f"  observations = {state.total_sample_count()}")
    return "\n".join(lines)


def parse_command(line: str) -> Tuple[str, List[str]]:
    """Tokenizes one line of input -- `str.split()`, nothing more."""
    tokens = line.strip().split()
    if not tokens:
        return "", []
    return tokens[0].lower(), tokens[1:]


# -- format_* : deterministic renderers of already-existing domain objects ---------------------------


def format_candidate(state: WorkbenchState, candidate: ActionCandidate) -> str:
    """One candidate's full inspection block -- `[n]` display number,
    identity, context, and (Phase 70) prediction/uncertainty/samples/
    information-value/utility/optimization status, all read directly off
    `state.session.predict`/`state.information_value_estimate`/
    `evaluate_decision`."""
    index = _display_index(state, candidate)
    prediction = state.session.predict(candidate)
    estimate = state.information_value_estimate(candidate)
    decision = evaluate_decision(state.candidates, state.session.state, state.session.iteration)
    optimization = next(o for o in decision.optimizations if o.candidate_id == candidate.id)
    lines = [
        f"[{index}] formulation={candidate.formulation.natural_key}",
        f"    process={state.session.iteration.query.process_natural_key}",
        f"    property={candidate.property}",
        f"    context={dict(candidate.target_context)}",
        f"    id={_short(candidate.id)}",
        "",
        f"    prediction: {_fmt_optional(prediction.predicted_value)}",
        f"    uncertainty: {_fmt_optional(prediction.uncertainty)}",
        f"    samples: {prediction.sample_count}",
        f"    information value: {estimate.estimate_status} ({_fmt_optional(estimate.estimate)})",
        f"    utility: {_fmt_optional(optimization.utility.utility)} ({optimization.status})",
    ]
    return "\n".join(lines)


def format_prediction(state: WorkbenchState, candidate: ActionCandidate, prediction: Prediction) -> str:
    return (
        f"Prediction for candidate [{_display_index(state, candidate)}]\n"
        f"  state: {_short(prediction.state_id)}\n"
        f"  predicted_value: {_fmt_optional(prediction.predicted_value)}\n"
        f"  uncertainty: {_fmt_optional(prediction.uncertainty)}\n"
        f"  sample_count: {prediction.sample_count}"
    )


def format_decision(state: WorkbenchState, optimization: OptimizationResult) -> str:
    selected = [o for o in optimization.optimizations if o.status == "SELECTED"]
    lines = ["Decision", "--------", ""]

    def _candidate_line(o: CandidateOptimization) -> str:
        candidate = next(c for c in state.list_candidates() if c.id == o.candidate_id)
        return f"Candidate {_display_index(state, candidate)}\n    utility: {_fmt_optional(o.utility.utility)} ({o.utility.utility_status})"

    for o in optimization.optimizations:
        lines.append(_candidate_line(o))
        lines.append("")

    if selected:
        chosen_candidate = next(c for c in state.list_candidates() if c.id == selected[0].candidate_id)
        lines.append(f"Recommended candidate: [{_display_index(state, chosen_candidate)}]")
        lines.append("Reason:")
        lines.append(f"    highest current utility (policy: max_candidates={optimization.policy.max_candidates})")
        lines.append("")
        lines.append("No action has been selected.")
        lines.append(f"Use: select {_display_index(state, chosen_candidate)}")
    else:
        lines.append("No candidate could be selected under the current policy (see `candidates` for why).")
        lines.append("No action has been selected.")
    return "\n".join(lines)


def format_selection(state: WorkbenchState, candidate: ActionCandidate) -> str:
    index = _display_index(state, candidate)
    return (
        f"Selected candidate [{index}] (property={candidate.property}, context={dict(candidate.target_context)})\n"
        "\n"
        "No experiment has been executed.\n"
        "The next real observation must be supplied externally.\n"
        "\n"
        "Use:\n"
        f"    observe <value>"
    )


def format_counterfactual(state: WorkbenchState, candidate: ActionCandidate, real_session_changed: bool) -> str:
    outcome = state.last_counterfactual
    assert outcome is not None
    estimate_after = state.information_value_estimate(candidate, outcome.projected_state)
    return (
        "Counterfactual exploration\n"
        "--------------------------\n"
        "\n"
        f"candidate: [{_display_index(state, candidate)}]\n"
        f"hypothetical value: {outcome.hypothetical_value}\n"
        f"source state: {_short(outcome.source_state_id)}\n"
        f"projected state: {_short(outcome.projected_state_id)}\n"
        "\n"
        f"prediction after hypothetical update: {_fmt_optional(outcome.delta.to_predicted_value)}\n"
        f"delta: predicted_value={_fmt_optional(outcome.delta.delta_predicted_value)}  "
        f"uncertainty={_fmt_optional(outcome.delta.delta_uncertainty)}\n"
        f"information value after (hypothetical): {estimate_after.estimate_status} "
        f"({_fmt_optional(estimate_after.estimate)})\n"
        "\n"
        "This branch is hypothetical.\n"
        "It has NOT been admitted as evidence.\n"
        f"The live session is unchanged: {'NO -- this would be a bug' if real_session_changed else 'confirmed'}"
    )


def format_assessment(
    state: WorkbenchState, candidate: ActionCandidate, predecessor_state_id: str,
    prediction: Prediction, assessment: PredictionAssessment,
) -> str:
    samples_for_candidate = state.session.predict(candidate).sample_count
    observed_unit = assessment.result.content.get("unit", "")
    return (
        "Observation -- this value is an externally supplied experimental observation\n"
        "------------------------------------------------------------------------------\n"
        f"candidate: [{_display_index(state, candidate)}]\n"
        f"observed: {assessment.observed_value} {observed_unit}\n"
        "\n"
        f"prediction: {_fmt_optional(prediction.predicted_value)}\n"
        f"residual: {_fmt_signed(assessment.residual)}\n"
        f"absolute residual: {_fmt_optional(assessment.absolute_residual)}\n"
        "\n"
        "State transition:\n"
        f"    S_t     = {_short(predecessor_state_id)}\n"
        f"    S_t+1   = {_short(state.session.state.id)}\n"
        "\n"
        f"samples for candidate: {samples_for_candidate}\n"
        "\n"
        "The previous session remains immutable."
    )


def format_transition(index: int, d: StateTransitionDiagnostic) -> str:
    """The narrative view `history` uses -- exactly the fields Phase 71
    sec.5 requires: state_before, candidate (implicit -- the whole
    listing is scoped to one), predicted_value_before, observed_value,
    signed_residual, state_after."""
    lines = [f"  [{index}] state_before={_short(d.predecessor_state_id)}  state_after={_short(d.successor_state_id)}"]
    lines.append(f"      predicted_value_before: {_fmt_optional(d.previous_prediction.predicted_value)}")
    if d.assessment is None:
        lines.append("      observed_value: (no observation recorded for this transition)")
        lines.append("      signed_residual: n/a")
    else:
        lines.append(f"      observed_value: {d.observation_value}")
        lines.append(f"      signed_residual: {_fmt_signed(d.residual_against_previous_prediction)}")
    return "\n".join(lines)


def format_diagnostic(index: int, d: StateTransitionDiagnostic) -> str:
    """The full-detail view `diagnostics` uses -- every field
    `materials.diagnostics.StateTransitionDiagnostic` carries, exposed
    directly rather than reimplemented (Phase 71 sec.6)."""
    lines = [f"  [{index}] {_short(d.predecessor_state_id)} -> {_short(d.successor_state_id)}"]
    lines.append(f"      model_state_key: {_short(d.model_state_key)}")
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


# -- command handlers : thin parsing/dispatch around the format_* renderers above ---------------------


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
    lines = ["Candidates", "----------", ""]
    for candidate in candidates:
        lines.append(format_candidate(state, candidate))
        lines.append("")
    return "\n".join(lines).rstrip()


def _cmd_decide(state: WorkbenchState) -> str:
    optimization = state.decide()
    return format_decision(state, optimization)


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
    return format_selection(state, candidate)


def _cmd_predict(state: WorkbenchState) -> str:
    try:
        prediction = state.predict()
    except ValueError as e:
        return str(e)
    assert state.selected_candidate is not None  # guaranteed: state.predict() above only succeeds once one is selected
    return format_prediction(state, state.selected_candidate, prediction)


def _cmd_explore(state: WorkbenchState, args: List[str]) -> str:
    if len(args) != 1:
        return "usage: explore <value>"
    try:
        hypothetical_value = float(args[0])
    except ValueError:
        return f"'{args[0]}' is not a numeric value"
    pre_state_id = state.session.state.id
    try:
        state.explore(hypothetical_value)
    except ValueError as e:
        return str(e)
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed: state.explore() above only succeeds once one is selected
    real_session_changed = state.session.state.id != pre_state_id
    return format_counterfactual(state, candidate, real_session_changed)


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
    return format_assessment(state, candidate, predecessor_state_id, prediction, assessment)


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
    lines.extend(format_transition(i, d) for i, d in enumerate(diagnostic_set.diagnostics, start=1))
    return "\n".join(lines)


def _cmd_diagnostics(state: WorkbenchState) -> str:
    """The same `StateTransitionDiagnosticSet` `history` renders,
    formatted with `format_diagnostic` (full `materials.diagnostics`
    detail) instead of `format_transition` (narrative summary) -- see
    module docstring, Phase 71 sec.6. Not a second computation: `state.
    history()` is called exactly the way `_cmd_history` above calls it."""
    try:
        diagnostic_set = state.history()
    except ValueError as e:
        return str(e)
    if not diagnostic_set.diagnostics:
        return "No transitions yet for the selected candidate -- observe at least one value first."
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed: state.history() above only succeeds once one is selected
    lines = [
        f"Diagnostics for candidate [{_display_index(state, candidate)}] "
        f"({len(diagnostic_set.diagnostics)} transition(s)):"
    ]
    lines.extend(format_diagnostic(i, d) for i, d in enumerate(diagnostic_set.diagnostics, start=1))
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
    if command == "diagnostics":
        return _cmd_diagnostics(state)
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
    print(format_scenario_banner(state))
    print()
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


def _load_scenario_state(path: str) -> WorkbenchState:
    """`--scenario <path>`: the smallest natural extension over `run_repl`'s
    existing `state` parameter (Phase 73) -- reads a plain JSON scenario
    DEFINITION (formulations/property/criterion/contexts, never
    observations/predictions/residuals) with only the standard library
    `json` module, and hands it to `workbench.interaction.
    bootstrap_research_scenario` unmodified. No schema framework, no new
    parsing beyond `json.load` plus that function's own minimal
    structural checks."""
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    return bootstrap_research_scenario(config)


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == "--scenario":
        try:
            state = _load_scenario_state(argv[1])
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Could not load scenario {argv[1]!r}: {e}", file=sys.stderr)
            return 1
        run_repl(state=state)
        return 0
    run_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
