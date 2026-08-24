"""workbench.cli: the workbench's user-facing surface -- command
parsing and presentation only. Every number rendered here is read
directly off a domain object `workbench.interaction.WorkbenchState` (or
a `materials.*`/`experiment.*` object it already produced); this module
computes nothing, and interprets nothing.

`dispatch()` returns text rather than printing, so the entire
interaction surface is callable from a test with no stdin/stdout
involved. `run_repl()` is the only function here that touches a
terminal.

No CLI framework, no third-party dependency: `parse_command`/`dispatch`/
`run_repl` are plain functions over `str`/`WorkbenchState`, using only
the standard library plus `workbench.theme` for layout.

PRESENTATION CONTRACT -- the rules every view below holds to, so the
interface reads as one instrument rather than a set of commands:

  ONE FRAME VOCABULARY. Every view is a `theme.panel`: a titled rule, a
  padded body, a closing rule. A single rule means established fact; a
  DOUBLE rule means hypothetical (used by, and only by, `explore`). An
  error is a panel too -- a state of the interface, not a break in it.

  LABELS LEFT, VALUES ALIGNED. Uppercase dim labels at a fixed width,
  values on a common column, units dim and trailing. A reader scans one
  column, not a paragraph.

  UNDETERMINED IS A WORD. A quantity the model cannot determine renders
  as the literal token UNDETERMINED in amber -- never a dash, never a
  blank, never zero. This is the interface's single most important
  honesty rule and `theme.num` enforces it centrally.

  SIGN IS NEVER DROPPED. Residuals and deltas render through
  `theme.num(signed=True)`, so `+20.0` and `-25.0` are visually
  distinct at a glance. No residual is ever coloured by magnitude or
  direction: the interface reports residuals, it does not grade them.

  RECOMMENDATION IS NOT ACTION. `decide` renders its choice as an
  advisory with the literal command needed to act on it; only `select`
  changes what `predict`/`explore`/`observe` operate on. The two are
  never rendered in the same voice.

  INDICES ARE 1-BASED AND ZERO-PADDED (`01`, `02`) -- a presentation
  choice this module owns end to end. `WorkbenchState.select_candidate`
  and `list_candidates` remain plain 0-indexed sequence operations
  underneath; `_display_index` and `_cmd_select` are the only places
  the translation happens.
"""

from __future__ import annotations

import json
import sys
from typing import List, Optional, Sequence, Tuple

from materials.assessment import PredictionAssessment
from materials.candidates import ActionCandidate
from materials.diagnostics import StateTransitionDiagnostic
from materials.model_state import Prediction
from materials.optimization import OptimizationResult
from workbench import theme
from workbench.interaction import (
    WorkbenchState, bootstrap_multi_candidate_scenario, bootstrap_research_scenario, evaluate_decision,
)

PRODUCT = "S C O U T   R E T R I E V A L   A G E N T"
SUBTITLE = "EXPERIMENTAL WORKBENCH · DETERMINISTIC STATE ARCHITECTURE"

# Display-only abbreviations of `materials.optimization`'s own status
# vocabulary, so the decision table stays column-aligned. The full
# status is always available on the underlying `CandidateOptimization`.
_SHORT_STATUS = {
    "SELECTED": "selected",
    "ELIGIBLE_NOT_SELECTED": "eligible",
    "NOT_ELIGIBLE": "ineligible",
}

COMMAND_GROUPS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("inspect", (
        ("status", "session state, selection, latest residual"),
        ("candidates", "registry with predictions and utility"),
        ("predict", "model prediction for the active candidate"),
    )),
    ("decide", (
        ("decide", "utility landscape and recommendation"),
        ("select <n>", "make candidate n the active candidate"),
        ("explore <value>", "project a hypothetical outcome"),
    )),
    ("admit", (
        ("observe <value> [unit]", "admit an externally supplied result"),
    )),
    ("review", (
        ("history", "transition narrative for this candidate"),
        ("diagnostics", "full detail for every transition"),
    )),
    ("session", (
        ("help", "this reference"),
        ("quit", "end the session"),
    )),
)


# -- shared rendering helpers -----------------------------------------------------------------------


def _display_index(state: WorkbenchState, candidate: ActionCandidate) -> int:
    return state.list_candidates().index(candidate) + 1


def _candidate_line(state: WorkbenchState, candidate: ActionCandidate) -> str:
    """`01  baseline · tensile_strength · 25 C` -- the canonical
    one-line identity of a candidate, used everywhere a candidate is
    named so it is recognisable across every view."""
    sep = theme.paint(f" {theme.DOT} ", theme.STRUCTURE)
    return (
        theme.paint(theme.index(_display_index(state, candidate)), theme.ACCENT)
        + "  "
        + theme.paint(candidate.formulation.natural_key, theme.VALUE)
        + sep
        + theme.paint(candidate.property, theme.VALUE)
        + sep
        + theme.paint(theme.context(candidate.target_context), theme.VALUE)
    )


def _short_candidate_line(state: WorkbenchState, candidate: ActionCandidate) -> str:
    """The compact form used inside dense tables: formulation + context."""
    return (
        f"{candidate.formulation.natural_key} {theme.DOT} "
        f"{theme.context(candidate.target_context)}"
    )


def _no_selection_notice() -> str:
    return theme.notice(
        "no active candidate",
        "no candidate selected — this command operates on the active candidate.",
        hint="candidates   then   select <n>",
    )


def _unit_for(state: WorkbenchState) -> str:
    """The unit last admitted for the active candidate, if any --
    display only, read off the real `ExperimentalResult.content`, never
    inferred."""
    for assessment in reversed(state.assessments):
        unit = assessment.result.content.get("unit")
        if isinstance(unit, str) and unit:
            return unit
    return ""


# -- format_* : deterministic renderers of already-existing domain objects ---------------------------


def format_masthead() -> str:
    return theme.masthead([PRODUCT, SUBTITLE])


def format_scenario_banner(state: WorkbenchState) -> str:
    """The session header: which study is loaded, its configured search
    space, the full candidate roster numbered to match `select <n>`, and
    the current real-observation count -- so the whole space is visible
    before anything is typed."""
    candidates = state.list_candidates()
    body: List[str] = [""]

    scenario = state.scenario
    if scenario is not None:
        body.append(theme.paint(scenario.name, theme.BOLD, theme.VALUE))
        body.append("")
        body.append(theme.kv("process", theme.paint(scenario.process, theme.VALUE)))
        body.append(theme.kv("property", theme.paint(scenario.property, theme.VALUE)))
        body.append(theme.kv(
            "criterion",
            theme.paint(f"{scenario.criterion_operator} {theme.num(scenario.criterion_target)}", theme.VALUE),
        ))
        body.append(theme.kv("search space", theme.paint(scenario.describe_candidate_space(), theme.VALUE)))
        body.append("")

    body.append(theme.divider("candidates"))
    body.append("")
    if not candidates:
        body.append(theme.paint("no candidates generated for this scenario", theme.WARN))
    for candidate in candidates:
        body.append(_candidate_line(state, candidate))
    body.append("")
    body.append(theme.divider())
    body.append("")
    body.append(theme.kv("observations", theme.paint(str(state.total_sample_count()), theme.VALUE)))
    body.append("")

    return theme.panel(
        "research scenario", body,
        right=f"{len(candidates)} candidate{'s' if len(candidates) != 1 else ''}",
    )


def format_help() -> str:
    body: List[str] = [""]
    for group, commands in COMMAND_GROUPS:
        body.append(theme.divider(group))
        body.append("")
        for name, description in commands:
            body.append(
                "  " + theme.paint(theme.pad(name, 24), theme.ACCENT)
                + theme.paint(theme.truncate(description, theme.width() - 30), theme.LABEL)
            )
        body.append("")
    return theme.panel("command reference", body, right="workbench")


def format_status(state: WorkbenchState) -> str:
    body: List[str] = [""]
    body.append(theme.kv("model state", theme.ident(state.session.state.id)))
    body.append(theme.kv("transitions", theme.paint(str(len(state.session.state_history) - 1), theme.VALUE)))
    body.append(theme.kv("observations", theme.paint(str(state.total_sample_count()), theme.VALUE)))
    body.append(theme.kv("candidates", theme.paint(str(len(state.list_candidates())), theme.VALUE)))
    body.append("")

    body.append(theme.divider("active candidate"))
    body.append("")
    if state.selected_candidate is None:
        body.append(theme.kv("selection", theme.paint("none", theme.WARN)))
        body.append(theme.kv("", theme.paint("issue  select <n>  to choose one", theme.MUTED)))
    else:
        candidate = state.selected_candidate
        prediction = state.session.predict(candidate)
        body.append(theme.kv("selection", _candidate_line(state, candidate)))
        body.append(theme.kv("prediction", theme.quantity(prediction.predicted_value, _unit_for(state))))
        body.append(theme.kv("uncertainty", theme.quantity(prediction.uncertainty)))
        body.append(theme.kv("samples", theme.paint(str(prediction.sample_count), theme.VALUE)))
    body.append("")

    body.append(theme.divider("latest observation"))
    body.append("")
    if state.assessments:
        latest = state.assessments[-1]
        body.append(theme.kv("observed", theme.quantity(latest.observed_value, _unit_for(state))))
        body.append(theme.kv("residual", theme.quantity(latest.residual, _unit_for(state), signed=True)))
        body.append(theme.kv("observation", theme.ident(latest.observation.id)))
    else:
        body.append(theme.kv("recorded", theme.paint("none", theme.MUTED)))
    body.append("")

    body.append(theme.divider("counterfactual"))
    body.append("")
    if state.last_counterfactual is not None:
        outcome = state.last_counterfactual
        body.append(theme.kv("inspected", theme.quantity(outcome.hypothetical_value, _unit_for(state))))
        body.append(theme.kv("projected state", theme.ident(outcome.projected_state_id)))
        body.append(theme.kv("", theme.badge("hypothetical · not evidence", theme.WARN)))
    else:
        body.append(theme.kv("inspected", theme.paint("none", theme.MUTED)))
    body.append("")

    right = state.scenario.name if state.scenario is not None else None
    return theme.panel("session status", body, right=right)


def format_candidate(state: WorkbenchState, candidate: ActionCandidate, optimization) -> List[str]:
    prediction = state.session.predict(candidate)
    estimate = state.information_value_estimate(candidate)
    selected = state.selected_candidate is not None and state.selected_candidate.id == candidate.id

    marks: List[str] = []
    if selected:
        marks.append(theme.badge("active", theme.ACCENT, filled=True))
    if optimization is not None and optimization.status == "SELECTED":
        marks.append(theme.paint(theme.ARROW + " ", theme.ACCENT) + theme.badge("recommended", theme.ACCENT))

    header = _candidate_line(state, candidate)
    if marks:
        header = theme.pad(header, theme.width() - 6 - sum(theme.visible_len(m) + 2 for m in marks))
        header += "  ".join(marks)

    utility_value = theme.quantity(optimization.utility.utility) if optimization is not None else theme.paint(
        theme.UNDETERMINED, theme.WARN
    )
    rows: List[Tuple[str, str]] = [
        ("prediction", theme.quantity(prediction.predicted_value, _unit_for(state))),
        ("uncertainty", theme.quantity(prediction.uncertainty)),
        ("samples", theme.paint(str(prediction.sample_count), theme.VALUE)),
        ("information", theme.paint(
            estimate.estimate_status,
            theme.WARN if estimate.estimate is None else theme.VALUE,
        ) + (theme.paint(f"  {theme.num(estimate.estimate)}", theme.MUTED) if estimate.estimate is not None else "")),
        ("utility", utility_value),
        ("id", theme.ident(candidate.id)),
    ]
    return [header, *theme.tree(rows)]


def format_candidates(state: WorkbenchState) -> str:
    candidates = state.list_candidates()
    if not candidates:
        return theme.notice(
            "empty registry", "no candidates were generated for this scenario.", tone=theme.WARN,
        )
    decision = evaluate_decision(state.candidates, state.session.state, state.session.iteration)
    by_id = {o.candidate_id: o for o in decision.optimizations}

    body: List[str] = [""]
    for candidate in candidates:
        body.extend(format_candidate(state, candidate, by_id.get(candidate.id)))
        body.append("")
    return theme.panel(
        "candidate registry", body,
        right=f"{len(candidates)} candidate{'s' if len(candidates) != 1 else ''}",
    )


def format_prediction(state: WorkbenchState, candidate: ActionCandidate, prediction: Prediction) -> str:
    body = [
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        theme.kv("model state", theme.ident(prediction.state_id)),
        "",
        theme.divider("readout"),
        "",
        theme.kv("predicted value", theme.quantity(prediction.predicted_value, _unit_for(state))),
        theme.kv("uncertainty", theme.quantity(prediction.uncertainty)),
        theme.kv("samples", theme.paint(str(prediction.sample_count), theme.VALUE)),
        "",
    ]
    if prediction.predicted_value is None:
        body.append(theme.paint("No samples exist for this cell.", theme.MUTED))
        body.append(theme.paint("The model reports no value rather than assuming one.", theme.MUTED))
        body.append("")
    return theme.panel("prediction", body, right=f"candidate {theme.index(_display_index(state, candidate))}")


def format_decision(state: WorkbenchState, optimization: OptimizationResult) -> str:
    selected = [o for o in optimization.optimizations if o.status == "SELECTED"]

    body: List[str] = [""]
    body.append(
        theme.paint("  " + theme.pad("#", 5), theme.LABEL)
        + theme.paint(theme.pad("CANDIDATE", 38), theme.LABEL)
        + theme.paint(theme.pad("UTILITY", 14), theme.LABEL)
        + theme.paint("STATUS", theme.LABEL)
    )
    body.append(theme.divider())
    for option in optimization.optimizations:
        candidate = next(c for c in state.list_candidates() if c.id == option.candidate_id)
        is_selected = option.status == "SELECTED"
        status = (
            theme.paint(theme.ARROW + " ", theme.ACCENT) + theme.badge("selected", theme.ACCENT)
            if is_selected else theme.paint(_SHORT_STATUS.get(option.status, option.status.lower()), theme.MUTED)
        )
        body.append(
            "  " + theme.paint(theme.pad(theme.index(_display_index(state, candidate)), 5), theme.ACCENT)
            + theme.pad(
                theme.paint(theme.truncate(_short_candidate_line(state, candidate), 36),
                            theme.VALUE if is_selected else theme.LABEL),
                38,
            )
            + theme.pad(theme.quantity(option.utility.utility), 14)
            + status
        )
    body.append("")

    body.append(theme.divider("recommendation"))
    body.append("")
    if selected:
        chosen = next(c for c in state.list_candidates() if c.id == selected[0].candidate_id)
        n = theme.index(_display_index(state, chosen))
        body.append(theme.kv("candidate", _candidate_line(state, chosen)))
        body.append(theme.kv("basis", theme.paint("highest current utility", theme.VALUE)))
        body.append(theme.kv("utility", theme.quantity(selected[0].utility.utility)))
        body.append("")
        body.append(theme.paint("ADVISORY ONLY — no action has been taken.", theme.WARN))
        body.append(
            theme.paint("To act on this recommendation:  ", theme.MUTED)
            + theme.paint(f"select {n}", theme.ACCENT)
        )
    else:
        body.append(theme.paint("No candidate is selectable under the current policy.", theme.WARN))
        body.append(theme.paint("See `candidates` for each candidate's utility status.", theme.MUTED))
    body.append("")

    return theme.panel(
        "decision analysis", body, right=f"policy max_candidates={optimization.policy.max_candidates}",
    )


def format_selection(state: WorkbenchState, candidate: ActionCandidate) -> str:
    body = [
        "",
        theme.kv("active candidate", _candidate_line(state, candidate)),
        theme.kv("id", theme.ident(candidate.id)),
        "",
        theme.divider("status"),
        "",
        theme.paint("No experiment has been executed.", theme.VALUE),
        theme.paint("The next real observation must be supplied externally.", theme.MUTED),
        "",
        theme.paint("  observe <value>", theme.ACCENT)
        + theme.paint("     admit an externally obtained result", theme.MUTED),
        theme.paint("  explore <value>", theme.ACCENT)
        + theme.paint("     project a hypothetical one instead", theme.MUTED),
        "",
    ]
    return theme.panel("candidate selected", body, right=f"candidate {theme.index(_display_index(state, candidate))}")


def format_counterfactual(state: WorkbenchState, candidate: ActionCandidate, live_unchanged: bool) -> str:
    outcome = state.last_counterfactual
    assert outcome is not None  # guaranteed: only rendered after a successful state.explore()
    estimate_after = state.information_value_estimate(candidate, outcome.projected_state)
    unit = _unit_for(state)

    body = [
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        theme.kv("hypothetical", theme.quantity(outcome.hypothetical_value, unit), tone=theme.WARN),
        "",
        theme.divider("projection"),
        "",
        theme.kv("source state", theme.ident(outcome.source_state_id)),
        theme.kv("projected state", theme.ident(outcome.projected_state_id)),
        theme.kv("prediction after", theme.quantity(outcome.delta.to_predicted_value, unit)),
        theme.kv("Δ prediction", theme.quantity(outcome.delta.delta_predicted_value, signed=True)),
        theme.kv("Δ uncertainty", theme.quantity(outcome.delta.delta_uncertainty, signed=True)),
        theme.kv("information", theme.paint(
            estimate_after.estimate_status,
            theme.WARN if estimate_after.estimate is None else theme.VALUE,
        )),
        "",
        theme.divider("isolation"),
        "",
        theme.kv("evidence admitted", theme.badge("no", theme.WARN)),
        theme.kv("live session", theme.badge("unchanged" if live_unchanged else "CHANGED", theme.WARN)),
        theme.kv("model state", theme.ident(state.session.state.id)),
        "",
        theme.paint("This branch is hypothetical.", theme.WARN),
        theme.paint("It has NOT been admitted as evidence. The live session is unchanged.", theme.MUTED),
        "",
    ]
    return theme.panel(
        "counterfactual projection", body,
        right="hypothetical · not evidence", tone=theme.WARN, double=True,
    )


def format_assessment(
    state: WorkbenchState, candidate: ActionCandidate, predecessor_state_id: str,
    prediction: Prediction, assessment: PredictionAssessment,
) -> str:
    unit = assessment.result.content.get("unit")
    unit = unit if isinstance(unit, str) else ""
    samples = state.session.predict(candidate).sample_count

    body = [
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        theme.kv("provenance", theme.paint("externally supplied experimental observation", theme.VALUE)),
        theme.kv("observation", theme.ident(assessment.observation.id)),
        "",
        theme.divider("measurement"),
        "",
        theme.kv("predicted", theme.quantity(prediction.predicted_value, unit)),
        theme.kv("observed", theme.quantity(assessment.observed_value, unit)),
        theme.kv("residual", theme.quantity(assessment.residual, unit, signed=True)),
        theme.kv("abs residual", theme.quantity(assessment.absolute_residual, unit)),
        "",
        theme.divider("state transition"),
        "",
        theme.kv("S(t)", theme.ident(predecessor_state_id), upper=False),
        theme.kv("S(t+1)", theme.ident(state.session.state.id), upper=False),
        theme.kv("samples", theme.paint(str(samples), theme.VALUE)),
        "",
        theme.paint("Prior session retained and immutable.", theme.MUTED),
        "",
    ]
    return theme.panel("observation admitted", body, right="external source", tone=theme.OK)


def format_transition(index: int, d: StateTransitionDiagnostic, unit: str = "") -> List[str]:
    """The narrative view `history` uses: state before, prediction
    before, what was observed, the signed residual, state after."""
    header = (
        theme.paint(theme.index(index), theme.ACCENT) + "   "
        + theme.ident(d.predecessor_state_id)
        + theme.paint(f"  {theme.TRANSITION}  ", theme.STRUCTURE)
        + theme.ident(d.successor_state_id)
    )
    if d.assessment is None:
        rows = [
            ("predicted", theme.quantity(d.previous_prediction.predicted_value, unit)),
            ("observed", theme.paint("no observation for this candidate", theme.MUTED)),
            ("residual", theme.paint("n/a", theme.MUTED)),
        ]
    else:
        rows = [
            ("predicted", theme.quantity(d.previous_prediction.predicted_value, unit)),
            ("observed", theme.quantity(d.observation_value, unit)),
            ("residual", theme.quantity(d.residual_against_previous_prediction, unit, signed=True)),
        ]
    return [header, *theme.tree(rows, label_width=12)]


def format_diagnostic(index: int, d: StateTransitionDiagnostic, unit: str = "") -> List[str]:
    """The full-detail view `diagnostics` uses: every field
    `materials.diagnostics.StateTransitionDiagnostic` carries."""
    header = (
        theme.paint(theme.index(index), theme.ACCENT) + "   "
        + theme.ident(d.predecessor_state_id)
        + theme.paint(f"  {theme.TRANSITION}  ", theme.STRUCTURE)
        + theme.ident(d.successor_state_id)
    )
    rows: List[Tuple[str, str]] = [
        ("model_state_key", theme.ident(d.model_state_key)),
        ("prediction t", theme.quantity(d.previous_prediction.predicted_value, unit)),
        ("uncertainty t", theme.quantity(d.previous_prediction.uncertainty)),
        ("prediction t+1", theme.quantity(d.new_prediction.predicted_value, unit)),
        ("uncertainty t+1", theme.quantity(d.new_prediction.uncertainty)),
        ("Δ prediction", theme.quantity(d.delta_predicted_value, signed=True)),
        ("Δ uncertainty", theme.quantity(d.delta_uncertainty, signed=True)),
    ]
    if d.assessment is None:
        rows.append(("observation", theme.paint("none for this candidate", theme.MUTED)))
    else:
        rows.append(("observation", theme.quantity(d.observation_value, unit)))
        rows.append(("residual", theme.quantity(d.residual_against_previous_prediction, unit, signed=True)))
        rows.append(("abs residual", theme.quantity(d.absolute_residual, unit)))
    return [header, *theme.tree(rows, label_width=16)]


def _format_transition_panel(
    state: WorkbenchState, title: str, renderer, diagnostics: Sequence[StateTransitionDiagnostic],
) -> str:
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed: only rendered after a successful state.history()
    unit = _unit_for(state)
    body: List[str] = [""]
    body.append(theme.kv("candidate", _candidate_line(state, candidate)))
    body.append("")
    body.append(theme.divider())
    body.append("")
    for i, d in enumerate(diagnostics, start=1):
        body.extend(renderer(i, d, unit))
        body.append("")
    return theme.panel(
        title, body,
        right=f"candidate {theme.index(_display_index(state, candidate))} · "
              f"{len(diagnostics)} transition{'s' if len(diagnostics) != 1 else ''}",
    )


# -- command handlers : thin parsing/dispatch around the renderers above ------------------------------


def parse_command(line: str) -> Tuple[str, List[str]]:
    """Tokenizes one line of input -- `str.split()`, nothing more."""
    tokens = line.strip().split()
    if not tokens:
        return "", []
    return tokens[0].lower(), tokens[1:]


def _cmd_select(state: WorkbenchState, args: List[str]) -> str:
    if len(args) != 1:
        return theme.notice("invalid command", "select takes exactly one candidate number.", hint="select <n>")
    try:
        n = int(args[0])
    except ValueError:
        return theme.notice(
            "invalid candidate", f"{args[0]!r} is not a candidate number.",
            hint=f"select <n>   where n is 1..{len(state.list_candidates())}",
        )
    try:
        candidate = state.select_candidate(n - 1)
    except IndexError:
        return theme.notice(
            "candidate out of range",
            f"there is no candidate {theme.index(n)} in this scenario.",
            hint=f"candidates   then   select <n>   where n is 1..{len(state.list_candidates())}",
        )
    return format_selection(state, candidate)


def _cmd_predict(state: WorkbenchState) -> str:
    try:
        prediction = state.predict()
    except ValueError:
        return _no_selection_notice()
    assert state.selected_candidate is not None  # guaranteed by the successful state.predict() above
    return format_prediction(state, state.selected_candidate, prediction)


def _cmd_explore(state: WorkbenchState, args: List[str]) -> str:
    if len(args) != 1:
        return theme.notice("invalid command", "explore takes exactly one value.", hint="explore <value>")
    try:
        hypothetical_value = float(args[0])
    except ValueError:
        return theme.notice(
            "invalid value", f"{args[0]!r} is not a numeric value.", hint="explore <value>",
        )
    before = state.session.state.id
    try:
        state.explore(hypothetical_value)
    except ValueError:
        return _no_selection_notice()
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed by the successful state.explore() above
    return format_counterfactual(state, candidate, live_unchanged=state.session.state.id == before)


def _cmd_observe(state: WorkbenchState, args: List[str]) -> str:
    if not (1 <= len(args) <= 2):
        return theme.notice(
            "invalid command", "observe takes a value and an optional unit.", hint="observe <value> [unit]",
        )
    try:
        value = float(args[0])
    except ValueError:
        return theme.notice(
            "invalid value", f"{args[0]!r} is not a numeric value.", hint="observe <value> [unit]",
        )
    unit = args[1] if len(args) == 2 else None
    predecessor_state_id = state.session.state.id
    try:
        assessment, prediction = state.observe(value, unit)
    except ValueError as e:
        if "no candidate selected" in str(e):
            return _no_selection_notice()
        return theme.notice("observation rejected", str(e))
    candidate = state.selected_candidate
    assert candidate is not None  # guaranteed by the successful state.observe() above
    return format_assessment(state, candidate, predecessor_state_id, prediction, assessment)


def _cmd_history(state: WorkbenchState) -> str:
    try:
        diagnostic_set = state.history()
    except ValueError:
        return _no_selection_notice()
    if not diagnostic_set.diagnostics:
        return theme.notice(
            "no transitions yet",
            "this session has admitted no observations.",
            hint="observe <value>", tone=theme.WARN,
        )
    return _format_transition_panel(state, "transition history", format_transition, diagnostic_set.diagnostics)


def _cmd_diagnostics(state: WorkbenchState) -> str:
    try:
        diagnostic_set = state.history()
    except ValueError:
        return _no_selection_notice()
    if not diagnostic_set.diagnostics:
        return theme.notice(
            "no transitions yet",
            "this session has admitted no observations.",
            hint="observe <value>", tone=theme.WARN,
        )
    return _format_transition_panel(state, "transition diagnostics", format_diagnostic, diagnostic_set.diagnostics)


def dispatch(state: WorkbenchState, command: str, args: List[str]) -> str:
    """The full command table. Returns text to display; never prints
    directly, so this function -- and therefore the entire interaction
    surface -- is callable from a test with no stdin/stdout involved."""
    if command in ("", "help"):
        return format_help()
    if command == "status":
        return format_status(state)
    if command == "candidates":
        return format_candidates(state)
    if command == "decide":
        return format_decision(state, state.decide())
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
    return theme.notice(
        "unknown command", f"{command!r} is not a command.", hint="help   for the command reference",
    )


def format_prompt(state: WorkbenchState) -> str:
    """The prompt carries the one piece of context every command depends
    on -- which candidate is active -- so it never has to be re-checked
    with `status`."""
    if state.selected_candidate is None:
        location = theme.paint("workbench", theme.LABEL)
    else:
        location = (
            theme.paint("workbench", theme.LABEL)
            + theme.paint(f" {theme.DOT} ", theme.STRUCTURE)
            + theme.paint(theme.index(_display_index(state, state.selected_candidate)), theme.ACCENT)
        )
    return location + theme.paint(f" {theme.ARROW} ", theme.ACCENT)


def run_repl(state: Optional[WorkbenchState] = None) -> None:
    """The only function in this package that touches a real terminal.
    `state` defaults to a fresh `bootstrap_multi_candidate_scenario()` --
    there is no persistence, so every invocation starts from nothing."""
    if state is None:
        state = bootstrap_multi_candidate_scenario()
    print(format_masthead())
    print()
    print(format_scenario_banner(state))
    print()
    print(theme.paint("  help", theme.ACCENT) + theme.paint("  for commands   ", theme.MUTED)
          + theme.paint("quit", theme.ACCENT) + theme.paint("  to end the session", theme.MUTED))
    print()
    while True:
        try:
            line = input(format_prompt(state))
        except EOFError:
            print()
            return
        command, args = parse_command(line)
        output = dispatch(state, command, args)
        if output == "__QUIT__":
            print(theme.paint("  session ended · no state persisted", theme.MUTED))
            return
        print(output)
        print()


def _load_scenario_state(path: str) -> WorkbenchState:
    """`--scenario <path>`: reads a plain JSON scenario DEFINITION
    (formulations/property/criterion/contexts, never observations) with
    only the standard library `json` module, and hands it to
    `workbench.interaction.bootstrap_research_scenario` unmodified."""
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    return bootstrap_research_scenario(config)


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == "--scenario":
        try:
            state = _load_scenario_state(argv[1])
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            print(theme.notice("scenario not loaded", f"could not load {argv[1]!r}: {e}"), file=sys.stderr)
            return 1
        run_repl(state=state)
        return 0
    run_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
