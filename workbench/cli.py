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
from experiment.session import trajectory_of
from materials.diagnostics import diagnose_transitions
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

# Aliases, added only where they improve usability: `?` is the
# near-universal terminal request for help, `about` is the common
# word for a programme summary, and `q`/`exit` are what people type
# to leave. No abbreviation is invented for any other command.
ALIASES = {"?": "help", "about": "scenario", "q": "quit", "exit": "quit",
           "focus": "select", "why": "explain"}

COMMAND_GROUPS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("inspect", (
        ("scenario", "the research programme being investigated"),
        ("status", "session state, selection, recommendation, residual"),
        ("candidates", "registry with predictions and utility"),
        ("predict", "model prediction for the active candidate"),
        ("inspect [n|terms]", "everything computed about one candidate"),
    )),
    ("decide", (
        ("decide", "utility landscape and recommendation"),
        ("explain", "why the last decision ranked as it did"),
        ("select <n|terms>", "activate a candidate by number or by name"),
        ("select clear", "deactivate the current candidate"),
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


def _coverage(state: WorkbenchState) -> Tuple[int, int]:
    """How many candidate cells carry at least one real sample, out of
    how many exist. Plain counting over `predict(...).sample_count` --
    no new statistic, and never presented as progress toward a goal."""
    candidates = state.list_candidates()
    observed = sum(1 for c in candidates if state.session.predict(c).sample_count > 0)
    return observed, len(candidates)


def _recommended_candidate(state: WorkbenchState) -> Optional[ActionCandidate]:
    """The candidate the existing optimization currently recommends, or
    `None` if the policy selects nothing. Read-only: uses
    `evaluate_decision` rather than `state.decide()`, so inspecting
    status never overwrites what the user's own last `decide` reported."""
    decision = evaluate_decision(state.candidates, state.session.state, state.session.iteration)
    for option in decision.optimizations:
        if option.status == "SELECTED":
            return next(c for c in state.list_candidates() if c.id == option.candidate_id)
    return None


def format_scenario(state: WorkbenchState) -> str:
    """The research programme itself: what is being studied, under which
    conditions, against which criterion, and how much of the space has
    been measured. Answers "what am I operating?" without reading JSON
    or source."""
    scenario = state.scenario
    if scenario is None:
        return theme.notice(
            "no scenario loaded",
            "this session was constructed directly rather than from a research scenario.",
            hint="python -m workbench --scenario <file.json>", tone=theme.WARN,
        )

    observed, total = _coverage(state)
    body: List[str] = [""]
    body.append(theme.paint(scenario.name, theme.BOLD, theme.VALUE))
    body.append("")
    body.append(theme.kv("property", theme.paint(scenario.property, theme.VALUE)))
    body.append(theme.kv("process", theme.paint(scenario.process, theme.VALUE)))
    body.append(theme.kv("criterion", theme.paint(
        f"{scenario.property} {scenario.criterion_operator} {theme.num(scenario.criterion_target)}", theme.VALUE,
    )))
    body.append("")

    body.append(theme.divider("formulations"))
    body.append("")
    for formulation in scenario.formulations:
        body.append("  " + theme.paint(formulation, theme.VALUE))
    body.append("")

    body.append(theme.divider("experimental contexts"))
    body.append("")
    for ctx in scenario.contexts:
        body.append("  " + theme.paint(theme.context(ctx), theme.VALUE))
    body.append("")

    body.append(theme.divider("search space"))
    body.append("")
    body.append(theme.kv("candidates", theme.paint(str(total), theme.VALUE)
                         + theme.paint(f"   {scenario.describe_candidate_space()}", theme.MUTED)))
    body.append(theme.kv("measured cells", theme.paint(f"{observed} of {total}", theme.VALUE)))
    body.append(theme.kv("observations", theme.paint(str(state.total_sample_count()), theme.VALUE)))
    body.append("")

    return theme.panel(
        "research programme", body,
        right=f"{total} candidate{'s' if total != 1 else ''}",
    )


def format_status(state: WorkbenchState) -> str:
    observed, total = _coverage(state)
    body: List[str] = [""]
    if state.scenario is not None:
        body.append(theme.kv("study", theme.paint(state.scenario.name, theme.VALUE)))
        body.append(theme.kv("property", theme.paint(state.scenario.property, theme.VALUE)))
    body.append(theme.kv("model state", theme.ident(state.session.state.id)))
    body.append(theme.kv("transitions", theme.paint(str(len(state.session.state_history) - 1), theme.VALUE)))
    body.append(theme.kv("observations", theme.paint(str(state.total_sample_count()), theme.VALUE)))
    body.append(theme.kv("candidates", theme.paint(str(total), theme.VALUE)
                         + theme.paint(f"   {observed} measured", theme.MUTED)))
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

    body.append(theme.divider("current recommendation"))
    body.append("")
    recommended = _recommended_candidate(state)
    if recommended is None:
        body.append(theme.kv("recommended", theme.paint("none selectable under policy", theme.WARN)))
    else:
        body.append(theme.kv("recommended", _candidate_line(state, recommended)))
        if state.selected_candidate is not None and state.selected_candidate.id == recommended.id:
            body.append(theme.kv("", theme.paint("this is the active candidate", theme.MUTED)))
        else:
            body.append(theme.kv("", theme.paint(
                f"advisory only — issue  select {theme.index(_display_index(state, recommended))}  to act on it",
                theme.MUTED,
            )))
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
    if prediction.sample_count == 0:
        marks.append(theme.badge("unmeasured", theme.WARN))

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

    observed, total = _coverage(state)
    body: List[str] = [""]
    body.append(
        theme.kv("measured", theme.paint(f"{observed} of {total}", theme.VALUE)
                 + theme.paint(f"   {total - observed} carry no observation yet", theme.MUTED))
    )
    body.append("")
    body.append(theme.divider())
    body.append("")
    for candidate in candidates:
        body.extend(format_candidate(state, candidate, by_id.get(candidate.id)))
        body.append("")
    return theme.panel(
        "candidate registry", body,
        right=f"{len(candidates)} candidate{'s' if len(candidates) != 1 else ''}",
    )


def _readout_rows(
    state: WorkbenchState, candidate: ActionCandidate, prediction: Prediction, unit: str,
    *, at_state=None, delta=None,
) -> List[str]:
    """The IDENTICAL readout vocabulary `predict` and `explore` both
    render -- prediction, uncertainty, samples, information -- so the
    two views are immediately recognisable as projections of the same
    research state. Every value is read off the `Prediction` it is
    given; `explore` passes the one `materials.ensemble.project_outcome`
    already computed, so nothing is calculated twice.

    `delta` (a `PredictionDelta`, when the caller has one) appends the
    signed change against the real state on the same rows."""
    estimate = state.information_value_estimate(candidate, at_state)
    rows = [
        theme.kv("prediction", theme.quantity(prediction.predicted_value, unit)),
        theme.kv("uncertainty", theme.quantity(prediction.uncertainty)),
        theme.kv("samples", theme.paint(str(prediction.sample_count), theme.VALUE)),
        theme.kv("information", theme.paint(
            estimate.estimate_status, theme.WARN if estimate.estimate is None else theme.VALUE,
        )),
    ]
    if delta is not None:
        rows[0] = theme.pad(rows[0], 40) + theme.paint("Δ  ", theme.STRUCTURE) + theme.quantity(
            delta.delta_predicted_value, signed=True)
        rows[1] = theme.pad(rows[1], 40) + theme.paint("Δ  ", theme.STRUCTURE) + theme.quantity(
            delta.delta_uncertainty, signed=True)
    return rows


def format_prediction(state: WorkbenchState, candidate: ActionCandidate, prediction: Prediction) -> str:
    """The REAL-state projection. Same frame vocabulary as `explore`,
    single-ruled and rooted at the real state -- the lineage tree stops
    at PREDICTION because nothing hypothetical is involved."""
    body = [
        "",
        *theme.lineage([
            ("real state", theme.ident(prediction.state_id)),
            ("prediction", theme.paint("from admitted evidence in this cell", theme.MUTED)),
        ]),
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        "",
        theme.divider("readout"),
        "",
        *_readout_rows(state, candidate, prediction, _unit_for(state)),
        "",
    ]
    if prediction.predicted_value is None:
        body.append(theme.paint("No samples exist for this cell.", theme.MUTED))
        body.append(theme.paint("The model reports no value rather than assuming one.", theme.MUTED))
        body.append("")
    return theme.panel(
        "projection · real state", body,
        right=f"candidate {theme.index(_display_index(state, candidate))}",
    )


def _transitions_for(state: WorkbenchState, candidate: ActionCandidate):
    """Every real transition whose assessment belongs to this candidate,
    matched by `candidate_id` -- never by list position. Reads the
    `StateTransitionDiagnosticSet` `materials.diagnostics` already
    produced for the session's own trajectory."""
    trajectory = trajectory_of(state.session)
    diagnostics = diagnose_transitions(trajectory, candidate, tuple(state.assessments))
    return [d for d in diagnostics.diagnostics if d.assessment is not None]


def format_inspection(state: WorkbenchState, candidate: ActionCandidate) -> str:
    """The complete computational state relevant to one candidate. A
    projection over existing objects -- `ActionCandidate`, `Prediction`,
    `InformationValueEstimate`, `CandidateOptimization`,
    `StateTransitionDiagnostic` -- with no data model of its own."""
    prediction = state.session.predict(candidate)
    estimate = state.information_value_estimate(candidate)
    decision = evaluate_decision(state.candidates, state.session.state, state.session.iteration)
    optimization = next(o for o in decision.optimizations if o.candidate_id == candidate.id)
    transitions = _transitions_for(state, candidate)
    unit = _unit_for(state)
    measured = prediction.sample_count > 0

    body: List[str] = [
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        theme.kv("formulation", theme.paint(candidate.formulation.natural_key, theme.VALUE)),
        theme.kv("property", theme.paint(candidate.property, theme.VALUE)),
        theme.kv("context", theme.paint(theme.context(candidate.target_context), theme.VALUE)),
        "",
        theme.divider("identity"),
        "",
        theme.kv("candidate_id", theme.ident(candidate.id, 24)),
        theme.kv("model_state_key", theme.ident(prediction.model_state_key, 24)),
        theme.kv("model state", theme.ident(prediction.state_id, 24)),
        "",
        theme.divider("computed state"),
        "",
        theme.kv("basis", theme.badge("real state", theme.ACCENT)
                 + theme.paint("   admitted evidence, not a projection", theme.MUTED)),
        theme.kv("measured", theme.badge("yes", theme.ACCENT) if measured else theme.badge("no", theme.WARN)),
        theme.kv("samples", theme.paint(str(prediction.sample_count), theme.VALUE)),
        theme.kv("prediction", theme.quantity(prediction.predicted_value, unit)),
        theme.kv("uncertainty", theme.quantity(prediction.uncertainty)),
        theme.kv("information", theme.paint(
            estimate.estimate_status, theme.WARN if estimate.estimate is None else theme.VALUE)),
        theme.kv("utility", theme.quantity(optimization.utility.utility)
                 + ("" if estimate.estimate is not None else theme.paint(
                     "   from exploration policy, not a measured quantity", theme.MUTED))),
        theme.kv("optimization", theme.paint(
            _SHORT_STATUS.get(optimization.status, optimization.status.lower()),
            theme.ACCENT if optimization.status == "SELECTED" else theme.MUTED)),
        "",
        theme.divider("observed history"),
        "",
    ]
    if not transitions:
        body.append(theme.paint("No observation has been admitted for this candidate.", theme.WARN))
        body.append(theme.paint("Its prediction rests on no evidence at all.", theme.MUTED))
    else:
        last = transitions[-1]
        body.append(theme.kv("transitions", theme.paint(str(len(transitions)), theme.VALUE)))
        body.append(theme.kv("last observed", theme.quantity(last.observation_value, unit)))
        body.append(theme.kv("last residual", theme.quantity(
            last.residual_against_previous_prediction, unit, signed=True)))
        body.append(theme.kv("last transition", theme.transition(
            theme.ident(last.predecessor_state_id), theme.ident(last.successor_state_id))))
    body.append("")
    return theme.panel(
        "candidate inspection", body,
        right=f"candidate {theme.index(_display_index(state, candidate))}",
    )


def format_explanation(state: WorkbenchState, optimization: OptimizationResult) -> str:
    """Explains an EXISTING computation -- which candidate the policy
    recommended, what each alternative received, which inputs were
    undetermined, and what changed since the last decision. Reports
    computational facts only: no causal or scientific claim is made
    about any material."""
    selected = [o for o in optimization.optimizations if o.status == "SELECTED"]
    body: List[str] = [""]

    if not selected:
        body.append(theme.paint("No candidate is selectable under the current policy.", theme.WARN))
        body.append(theme.paint("Every candidate's utility is undetermined, so none can rank.", theme.MUTED))
        body.append("")
        return theme.panel("decision explanation", body, right="no recommendation")

    chosen = next(c for c in state.list_candidates() if c.id == selected[0].candidate_id)
    body.append(theme.kv("recommended", _candidate_line(state, chosen)))
    body.append(theme.kv("utility", theme.quantity(selected[0].utility.utility)))
    body.append(theme.kv("policy", theme.paint(
        f"max_candidates={optimization.policy.max_candidates}", theme.VALUE)))
    body.append(theme.kv("reason", theme.paint(
        "highest determinate utility among eligible candidates", theme.VALUE)))
    body.append("")

    body.append(theme.divider("alternatives considered"))
    body.append("")
    for option in optimization.optimizations:
        candidate = next(c for c in state.list_candidates() if c.id == option.candidate_id)
        mark = theme.paint(theme.ARROW, theme.ACCENT) if option.status == "SELECTED" else " "
        body.append(
            f"  {mark} " + theme.paint(theme.index(_display_index(state, candidate)), theme.ACCENT) + "  "
            + theme.pad(theme.truncate(_short_candidate_line(state, candidate), 26), 28)
            + theme.pad(theme.quantity(option.utility.utility), 12)
            + theme.paint(_SHORT_STATUS.get(option.status, option.status.lower()), theme.MUTED)
        )
    body.append("")

    body.append(theme.divider("contributing inputs"))
    body.append("")
    body.append(
        "  " + theme.paint(theme.pad("  #", 6), theme.LABEL)
        + theme.paint(theme.pad("SAMPLES", 10), theme.LABEL)
        + theme.paint(theme.pad("UNCERTAINTY", 16), theme.LABEL)
        + theme.paint("INFORMATION", theme.LABEL)
    )
    undetermined: List[str] = []
    for option in optimization.optimizations:
        candidate = next(c for c in state.list_candidates() if c.id == option.candidate_id)
        prediction = state.session.predict(candidate)
        estimate = state.information_value_estimate(candidate)
        n = theme.index(_display_index(state, candidate))
        body.append(
            "    " + theme.pad(theme.paint(n, theme.ACCENT), 4)
            + theme.pad(theme.paint(str(prediction.sample_count), theme.VALUE), 10)
            + theme.pad(theme.quantity(prediction.uncertainty), 16)
            + theme.paint(
                estimate.estimate_status, theme.WARN if estimate.estimate is None else theme.VALUE)
        )
        if estimate.estimate is None:
            undetermined.append(n)
    body.append("")

    if undetermined:
        body.append(theme.paint(
            f"  Candidates {', '.join(undetermined)}", theme.WARN))
        body.append(theme.paint(
            "  have no computable information value.", theme.WARN))
        body.append(theme.paint(
            "  Their utility input came from the workbench's explicit", theme.MUTED))
        body.append(theme.paint(
            "  exploration policy, not from a measured quantity.", theme.MUTED))
        body.append(theme.paint(
            "  See workbench.interaction._utility_input_for.", theme.MUTED))
        body.append("")

    previous = state.previous_decision
    body.append(theme.divider("change since last decision"))
    body.append("")
    if previous is None:
        body.append(theme.paint("This is the first decision in this session.", theme.MUTED))
    else:
        previous_selected = [o for o in previous.optimizations if o.status == "SELECTED"]
        previous_id = previous_selected[0].candidate_id if previous_selected else None
        if previous_id is not None:
            was = next(c for c in state.list_candidates() if c.id == previous_id)
            body.append(theme.kv("previously", _candidate_line(state, was)))
        else:
            body.append(theme.kv("previously", theme.paint("no candidate was selectable", theme.WARN)))
        body.append(theme.kv("now", _candidate_line(state, chosen)))
        body.append("")
        if previous_id == chosen.id:
            body.append(theme.paint("  The recommendation is unchanged.", theme.VALUE))
        else:
            body.append(theme.paint(
                "  The recommendation changed because the computed", theme.VALUE))
            body.append(theme.paint(
                "  utility landscape changed.", theme.VALUE))
        body.append(theme.paint(
            "  No claim is made about any material — only about the computation.", theme.MUTED))
    body.append("")

    return theme.panel(
        "decision explanation", body,
        right=f"policy max_candidates={optimization.policy.max_candidates}",
    )


def format_decision(state: WorkbenchState, optimization: OptimizationResult) -> str:
    selected = [o for o in optimization.optimizations if o.status == "SELECTED"]

    body: List[str] = [""]
    body.append(
        theme.paint("  " + theme.pad("#", 4), theme.LABEL)
        + theme.paint(theme.pad("CANDIDATE", 30), theme.LABEL)
        + theme.paint(theme.pad("SAMPLES", 9), theme.LABEL)
        + theme.paint(theme.pad("UTILITY", 11), theme.LABEL)
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
            "  " + theme.paint(theme.pad(theme.index(_display_index(state, candidate)), 4), theme.ACCENT)
            + theme.pad(
                theme.paint(theme.truncate(_short_candidate_line(state, candidate), 28),
                            theme.VALUE if is_selected else theme.LABEL),
                30,
            )
            + theme.pad(theme.paint(str(state.session.predict(candidate).sample_count), theme.VALUE), 9)
            + theme.pad(theme.quantity(option.utility.utility), 11)
            + status
        )
    body.append("")

    body.append(theme.divider("recommendation"))
    body.append("")
    if selected:
        chosen = next(c for c in state.list_candidates() if c.id == selected[0].candidate_id)
        n = theme.index(_display_index(state, chosen))
        prediction = state.session.predict(chosen)
        estimate = state.information_value_estimate(chosen)
        body.append(theme.kv("candidate", _candidate_line(state, chosen)))
        body.append(theme.kv("prediction", theme.quantity(prediction.predicted_value, _unit_for(state))))
        body.append(theme.kv("uncertainty", theme.quantity(prediction.uncertainty)))
        body.append(theme.kv("samples", theme.paint(str(prediction.sample_count), theme.VALUE)))
        body.append(theme.kv("information", theme.paint(
            estimate.estimate_status, theme.WARN if estimate.estimate is None else theme.VALUE,
        )))
        body.append(theme.kv("utility", theme.quantity(selected[0].utility.utility)))
        body.append(theme.kv("basis", theme.paint("highest current utility under this policy", theme.VALUE)))
        # the next-highest determinate utility, shown for contrast -- both values are already
        # computed by materials.optimization; nothing is derived from them here.
        others = [
            o for o in optimization.optimizations
            if o.candidate_id != chosen.id and o.utility.utility is not None
        ]
        if others:
            runner_up = max(others, key=lambda o: o.utility.utility)  # type: ignore[arg-type,return-value]
            runner_candidate = next(c for c in state.list_candidates() if c.id == runner_up.candidate_id)
            body.append(theme.kv("next highest", theme.quantity(runner_up.utility.utility)
                                 + theme.paint(f"   candidate {theme.index(_display_index(state, runner_candidate))}",
                                               theme.MUTED)))
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
    """The HYPOTHETICAL projection. Deliberately the same frame, the
    same lineage tree and the same readout rows as `format_prediction`
    -- but double-ruled, amber, and rooted one branch deeper, so the
    user reads it as the same instrument pointed at a branch that is
    not evidence."""
    outcome = state.last_counterfactual
    assert outcome is not None  # guaranteed: only rendered after a successful state.explore()
    unit = _unit_for(state)

    body = [
        "",
        *theme.lineage([
            ("real state", theme.ident(outcome.source_state_id)),
            ("hypothetical", theme.paint(f"y = {theme.num(outcome.hypothetical_value)}", theme.WARN)
             + (theme.paint(f" {unit}", theme.MUTED) if unit else "")),
            ("projected", theme.ident(outcome.projected_state_id)),
        ]),
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        "",
        theme.divider("readout · projected"),
        "",
        *_readout_rows(
            state, candidate, outcome.prediction_after, unit,
            at_state=outcome.projected_state, delta=outcome.delta,
        ),
        "",
        theme.divider("isolation"),
        "",
        theme.kv("admitted", theme.badge("no", theme.WARN)
                 + theme.paint("   nothing was written to the evidence pool", theme.MUTED)),
        theme.kv("live session", theme.badge("unchanged" if live_unchanged else "CHANGED", theme.WARN)),
        theme.kv("real state", theme.ident(state.session.state.id)),
        "",
        theme.paint("NOT REAL EVIDENCE.", theme.WARN),
        theme.paint("This branch is hypothetical. It has NOT been admitted as evidence,", theme.MUTED),
        theme.paint("and the real session is unchanged.", theme.MUTED),
        "",
    ]
    return theme.panel(
        "projection · hypothetical branch", body,
        right="hypothetical · not evidence", tone=theme.WARN, double=True,
    )


def format_assessment(
    state: WorkbenchState, candidate: ActionCandidate, predecessor_state_id: str,
    prediction: Prediction, assessment: PredictionAssessment,
) -> str:
    """An observation rendered as a STATE TRANSITION, not a printed
    number. `prediction` is the projection that existed immediately
    before admission; `after` is the one the advanced session reports
    now. Both already exist -- the before/after columns pair them, they
    do not recompute anything."""
    unit = assessment.result.content.get("unit")
    unit = unit if isinstance(unit, str) else ""
    after = state.session.predict(candidate)

    body = [
        "",
        theme.kv("candidate", _candidate_line(state, candidate)),
        theme.kv("context", theme.paint(theme.context(candidate.target_context), theme.VALUE)),
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
        theme.kv("samples", theme.transition(
            theme.paint(str(prediction.sample_count), theme.VALUE),
            theme.paint(str(after.sample_count), theme.VALUE),
        )),
        theme.kv("prediction", theme.transition(
            theme.quantity(prediction.predicted_value, unit), theme.quantity(after.predicted_value, unit),
        )),
        theme.kv("uncertainty", theme.transition(
            theme.quantity(prediction.uncertainty), theme.quantity(after.uncertainty),
        )),
        theme.kv("state", theme.transition(
            theme.ident(predecessor_state_id), theme.ident(state.session.state.id),
        )),
        "",
        theme.paint("Prior session retained and immutable.", theme.MUTED),
        "",
    ]
    return theme.panel("observation accepted", body, right="external source", tone=theme.OK)


def format_transition(index: int, d: StateTransitionDiagnostic, unit: str = "") -> List[str]:
    """RESEARCH CHRONOLOGY: what was expected, what came back, how far
    off it was, and where the state moved. Same identifiers and the same
    `theme.transition` vocabulary diagnostics uses, so one transition is
    recognisable in both views."""
    header = theme.paint(theme.index(index), theme.ACCENT) + "   " + theme.paint(
        _short_candidate_line_from(d), theme.VALUE)
    observed = (
        theme.paint("no observation for this candidate", theme.MUTED) if d.assessment is None
        else theme.quantity(d.observation_value, unit)
    )
    rows = [
        ("prediction → observation", theme.transition(
            theme.quantity(d.previous_prediction.predicted_value, unit), observed, width_before=18)),
        ("residual", theme.paint("n/a", theme.MUTED) if d.assessment is None
         else theme.quantity(d.residual_against_previous_prediction, unit, signed=True)),
        ("state", theme.transition(
            theme.ident(d.predecessor_state_id), theme.ident(d.successor_state_id), width_before=18)),
    ]
    return [header, *theme.tree(rows, label_width=26)]


def _short_candidate_line_from(d: StateTransitionDiagnostic) -> str:
    """The candidate/context label for a transition, taken from the
    embedded `Prediction` -- which already carries the formulation and
    the target context, so nothing is looked up or re-derived."""
    prediction = d.previous_prediction
    return f"{prediction.formulation.natural_key} {theme.DOT} {theme.context(prediction.context)}"


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
        ("candidate_id", theme.ident(d.candidate_id)),
        ("model_state_key", theme.ident(d.model_state_key)),
        ("state_t", theme.ident(d.predecessor_state_id)),
        ("state_t+1", theme.ident(d.successor_state_id)),
        ("samples t", theme.paint(str(d.previous_prediction.sample_count), theme.VALUE)),
        ("samples t+1", theme.paint(str(d.new_prediction.sample_count), theme.VALUE)),
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


def _context_tokens(candidate: ActionCandidate) -> set:
    """Every string a user could reasonably type to name this
    candidate's context, taken from the scenario's OWN representation --
    the raw values, the `key=value` form, and the rendered display form.
    Nothing is invented and nothing is fuzzy: each token is an exact
    string derived from the context mapping itself."""
    tokens = {theme.context(candidate.target_context).lower()}
    for key, value in dict(candidate.target_context).items():
        tokens.add(str(value).lower())
        tokens.add(f"{key}={value}".lower())
        if key.endswith("_c"):
            tokens.add(f"{value}c")
    return tokens


def _matches(candidate: ActionCandidate, constraints: List[Tuple[str, str]]) -> bool:
    for field, wanted in constraints:
        if field == "formulation":
            if candidate.formulation.natural_key.lower() != wanted:
                return False
        elif field == "property":
            if candidate.property.lower() != wanted:
                return False
        elif field == "context":
            if wanted not in _context_tokens(candidate):
                return False
        else:  # a bare token: it may name the formulation, the property, or the context
            if not (
                candidate.formulation.natural_key.lower() == wanted
                or candidate.property.lower() == wanted
                or wanted in _context_tokens(candidate)
            ):
                return False
    return True


def resolve_candidate(state: WorkbenchState, args: List[str]):
    """Resolve a human's words to EXACTLY ONE existing `ActionCandidate`,
    or return a `theme.notice` explaining why it could not.

    Accepts a display index (`select 1`, kept for compatibility) or
    semantic terms drawn from the scenario's own vocabulary:

        select baseline 80
        select formulation=baseline context=80
        select baseline @ 80

    Never fuzzy-matches, never creates a candidate, and never uses
    display position as identity: the returned object is the same
    `ActionCandidate` -- same `candidate.id` -- that prediction,
    decision, observation, history and diagnostics all use."""
    candidates = state.list_candidates()
    if not args:
        return theme.notice(
            "invalid command", "select needs a candidate.",
            hint="select <n>   or   select <formulation> <context>",
        )

    if len(args) == 1 and args[0].isdigit():
        n = int(args[0])
        if 1 <= n <= len(candidates):
            return candidates[n - 1]
        # out of registry range -- it may still be a context value, so keep resolving
        # semantically rather than dead-ending on a number the user did not mean as an index.
        if not any(args[0].lower() in _context_tokens(c) for c in candidates):
            return theme.notice(
                "candidate out of range", f"there is no candidate {theme.index(n)} in this scenario.",
                hint=f"candidates   then   select <n>   where n is 1..{len(candidates)}",
            )

    constraints: List[Tuple[str, str]] = []
    for token in args:
        if token == "@":  # a separator, not a term
            continue
        if "=" in token:
            field, _, value = token.partition("=")
            field = field.lower()
            if field in ("formulation", "property", "context"):
                constraints.append((field, value.lower()))
            elif any(field in {k.lower() for k in dict(c.target_context)} for c in candidates):
                # a real context key from the scenario, e.g. `temperature_c=80`
                constraints.append(("context", token.lower()))
            else:
                known = sorted({k for c in candidates for k in dict(c.target_context)})
                return theme.notice(
                    "unknown selector", f"{field!r} is not a selectable field.",
                    hint=f"formulation=  property=  context=  or a context key: {', '.join(known)}",
                )
        else:
            constraints.append(("", token.lower()))

    matches = [c for c in candidates if _matches(c, constraints)]
    if not matches:
        formulations = sorted({c.formulation.natural_key for c in candidates})
        contexts = sorted({theme.context(c.target_context) for c in candidates})
        return theme.panel("no such candidate", [
            theme.paint(f"nothing in this scenario matches {' '.join(args)!r}.", theme.VALUE),
            "",
            theme.kv("expected", theme.paint("select <formulation> <context>", theme.MUTED)),
            theme.kv("formulations", theme.paint(", ".join(formulations), theme.MUTED)),
            theme.kv("contexts", theme.paint(", ".join(contexts), theme.MUTED)),
        ], tone=theme.ERR)
    if len(matches) > 1:
        listing = "   ".join(
            f"{theme.index(_display_index(state, c))} {c.formulation.natural_key} "
            f"{theme.DOT} {theme.context(c.target_context)}"
            for c in matches[:6]
        )
        return theme.notice(
            "ambiguous candidate",
            f"{' '.join(args)!r} matches {len(matches)} candidates — say which.",
            hint=listing, tone=theme.WARN,
        )
    return matches[0]


def _cmd_select(state: WorkbenchState, args: List[str]) -> str:
    if len(args) == 1 and args[0].lower() == "clear":
        if state.selected_candidate is None:
            return theme.notice(
                "nothing selected", "no candidate is active, so there is nothing to clear.",
                hint="select <n>   or   select <formulation> <context>", tone=theme.WARN,
            )
        state.clear_selection()
        return theme.panel("selection cleared", [
            "", theme.paint("No candidate is active.", theme.VALUE),
            theme.paint("predict, explore and observe need one before they can run.", theme.MUTED), "",
            theme.paint("  select <n>", theme.ACCENT)
            + theme.paint("                  by registry number", theme.MUTED),
            theme.paint("  select <formulation> <context>", theme.ACCENT)
            + theme.paint("  by name", theme.MUTED), "",
        ])

    resolved = resolve_candidate(state, args)
    if isinstance(resolved, str):
        return resolved
    state.select_candidate(state.list_candidates().index(resolved))
    return format_selection(state, resolved)


def _cmd_inspect(state: WorkbenchState, args: List[str]) -> str:
    if not args:
        if state.selected_candidate is None:
            return _no_selection_notice()
        return format_inspection(state, state.selected_candidate)
    resolved = resolve_candidate(state, args)
    if isinstance(resolved, str):
        return resolved
    return format_inspection(state, resolved)


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
    if unit is not None:
        try:
            float(unit)
        except ValueError:
            pass
        else:
            return theme.notice(
                "invalid unit", f"{unit!r} is a number, not a unit of measurement.",
                hint="observe <value> [unit]   e.g.  observe 90 MPa",
            )
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
    command = ALIASES.get(command, command)
    if command in ("", "help"):
        return format_help()
    if command == "scenario":
        return format_scenario(state)
    if command == "status":
        return format_status(state)
    if command == "candidates":
        return format_candidates(state)
    if command == "decide":
        return format_decision(state, state.decide())
    if command == "inspect":
        return _cmd_inspect(state, args)
    if command == "explain":
        if state.last_decision is None:
            return theme.notice(
                "no decision yet", "nothing has been decided in this session.",
                hint="decide   then   explain", tone=theme.WARN,
            )
        return format_explanation(state, state.last_decision)
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
    if command == "quit":
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
