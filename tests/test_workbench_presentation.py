"""Phase 73 (interface): locks the workbench's visual system, so the
UI cannot silently regress.

These tests assert PRESENTATION invariants only -- frame integrity,
epistemic honesty of rendered values, colour degradation, and the
consistency rules `workbench/cli.py`'s presentation contract states.
Scientific behaviour is covered by the other workbench test files;
nothing here touches state, evidence, or the algebra.
"""

import json
from pathlib import Path

import pytest

from workbench import theme
from workbench.cli import (
    COMMAND_GROUPS, dispatch, format_masthead, format_prompt, format_scenario_banner,
)
from workbench.interaction import WorkbenchState, bootstrap_research_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_SCENARIO_PATH = REPO_ROOT / "examples" / "polymer_tensile_strength.json"

FRAME_STARTS = "┌│└╔║╚"

# every view, in the order a session actually exercises them, including
# each error state -- so a regression in any one of them fails here.
VIEW_SCRIPT = (
    ("help", []), ("scenario", []), ("status", []), ("candidates", []), ("decide", []),
    ("select", ["1"]), ("predict", []), ("explore", ["90"]),
    ("observe", ["80"]), ("observe", ["100"]),
    ("history", []), ("diagnostics", []), ("status", []),
    ("candidates", []), ("decide", []),
    ("select", ["99"]), ("select", ["x"]), ("select", []),
    ("observe", ["abc"]), ("observe", []), ("explore", ["abc"]), ("explore", []),
    ("bogus", []),
)


def _fixed_clock():
    counter = {"n": 0}

    def clock() -> str:
        n = counter["n"]
        counter["n"] += 1
        return f"2026-08-24T07:{n:02d}:00Z"

    return clock


@pytest.fixture()
def state() -> WorkbenchState:
    with open(EXAMPLE_SCENARIO_PATH, encoding="utf-8") as f:
        config = json.load(f)
    return bootstrap_research_scenario(config, clock=_fixed_clock())


@pytest.fixture(autouse=True)
def _plain_by_default():
    theme.set_color(False)
    yield
    theme.set_color(None)


def _rendered_views(state: WorkbenchState):
    yield "banner", format_scenario_banner(state)
    for command, args in VIEW_SCRIPT:
        yield command, dispatch(state, command, args)


# -- frame integrity ---------------------------------------------------------------------------------


@pytest.mark.parametrize("colored", [False, True])
def test_every_framed_line_is_exactly_frame_width(state: WorkbenchState, colored: bool):
    """The single most visible failure mode of a terminal UI is a ragged
    frame. Every bordered line in every view must measure exactly
    `theme.width()` -- identically with and without colour, since
    padding is computed on visible length."""
    theme.set_color(colored)
    for name, text in _rendered_views(state):
        for line in text.splitlines():
            plain = theme._ANSI.sub("", line)
            if plain[:1] in FRAME_STARTS:
                assert theme.visible_len(line) == theme.width(), f"{name}: ragged frame line {plain!r}"


def test_every_view_is_a_closed_frame(state: WorkbenchState):
    """Each view opens and closes its frame exactly once, and the two
    match style: a double rule opens only where a double rule closes."""
    for name, text in _rendered_views(state):
        plain = [theme._ANSI.sub("", line) for line in text.splitlines()]
        opens = [line for line in plain if line[:1] in "┌╔"]
        closes = [line for line in plain if line[:1] in "└╚"]
        assert len(opens) == 1, f"{name}: expected one opening rule"
        assert len(closes) == 1, f"{name}: expected one closing rule"
        assert (opens[0][0] == "╔") == (closes[0][0] == "╚"), f"{name}: mismatched frame style"


def test_long_content_is_clipped_rather_than_breaking_the_frame():
    """`panel` clips before padding, so no body line -- however long --
    can overflow. Verified directly, since a regression here would only
    show up in an unusual scenario."""
    text = theme.panel("test", ["x" * 500, "short"])
    for line in text.splitlines():
        assert theme.visible_len(line) == theme.width()
    assert "…" in text


# -- epistemic honesty in the rendering layer ---------------------------------------------------------


def test_none_always_renders_as_the_word_undetermined():
    assert theme.num(None) == "UNDETERMINED"
    assert theme.num(None, signed=True) == "UNDETERMINED"
    assert theme.quantity(None, "MPa") == "UNDETERMINED"  # no unit on a non-measurement
    assert "0" not in theme.num(None)


def test_zero_is_rendered_distinctly_from_undetermined():
    """A real zero is a determined value and must never be confusable
    with the absence of one."""
    assert theme.num(0.0) == "0.0"
    assert theme.num(0.0) != theme.num(None)


def test_signed_rendering_never_drops_direction():
    assert theme.num(20.0, signed=True) == "+20.0"
    assert theme.num(-20.0, signed=True) == "-20.0"
    assert theme.num(0.0, signed=True) == "0.0"
    # unsigned rendering still keeps a negative sign -- only `+` is optional
    assert theme.num(-20.0) == "-20.0"


def test_float_noise_is_rendered_readably_without_losing_the_value():
    assert theme.num(-0.09999999999999998) == "-0.1"
    assert theme.num(86.66666666666667) == "86.6667"
    assert theme.num(100.0) == "100.0"


def test_no_view_renders_an_undetermined_quantity_as_zero(state: WorkbenchState):
    """Across a full session, every row carrying UNDETERMINED carries no
    numeral -- the two are never mixed on one line."""
    for name, text in _rendered_views(state):
        for line in text.splitlines():
            if theme.UNDETERMINED in line:
                after = line.split(theme.UNDETERMINED, 1)[1]
                assert not any(ch.isdigit() for ch in after), f"{name}: numeral after UNDETERMINED: {line!r}"


# -- consistency rules from the presentation contract -------------------------------------------------


def test_only_the_counterfactual_view_uses_the_double_frame(state: WorkbenchState):
    """A double rule means hypothetical. If any other view adopted it,
    a projection could be mistaken for admitted evidence."""
    for name, text in _rendered_views(state):
        uses_double = any(theme._ANSI.sub("", line)[:1] in "╔╚║" for line in text.splitlines())
        assert uses_double == (name == "explore" and "COUNTERFACTUAL" in text), (
            f"{name}: double frame used outside the counterfactual view"
        )


def test_counterfactual_view_states_its_isolation_explicitly(state: WorkbenchState):
    dispatch(state, "select", ["1"])
    text = dispatch(state, "explore", ["90"])
    assert "HYPOTHETICAL" in text
    assert "NOT been admitted as evidence" in text
    assert "EVIDENCE ADMITTED" in text and "NO" in text
    assert "LIVE SESSION" in text and "UNCHANGED" in text


def test_decision_view_separates_recommendation_from_action(state: WorkbenchState):
    """`decide` must never read as though it acted. It states the
    advisory and the literal command required to act on it."""
    text = dispatch(state, "decide", [])
    assert "ADVISORY ONLY" in text
    assert "no action has been taken" in text.lower()
    assert "select " in text
    assert state.selected_candidate is None


def test_selection_view_states_that_no_experiment_was_run(state: WorkbenchState):
    text = dispatch(state, "select", ["1"])
    assert "No experiment has been executed." in text
    assert "supplied externally" in text


def test_observation_view_names_its_external_provenance(state: WorkbenchState):
    dispatch(state, "select", ["1"])
    text = dispatch(state, "observe", ["80"])
    assert "externally supplied experimental observation" in text
    assert "immutable" in text.lower()


def test_no_view_grades_a_result(state: WorkbenchState):
    """The interface reports; it does not judge. No view may describe a
    residual or a candidate in evaluative language."""
    forbidden = ("good", "bad", "better", "worse", "improved", "degraded",
                 "accurate", "inaccurate", "success", "failure", "poor", "excellent")
    for name, text in _rendered_views(state):
        lowered = text.lower()
        for word in forbidden:
            assert word not in lowered, f"{name}: evaluative language {word!r}"


def test_every_error_state_names_what_was_expected(state: WorkbenchState):
    """Every rejection tells the user the form that would have worked."""
    for command, args in (
        ("select", ["99"]), ("select", ["x"]), ("select", []),
        ("observe", ["abc"]), ("observe", []),
        ("explore", ["abc"]), ("explore", []), ("bogus", []),
    ):
        text = dispatch(state, command, args)
        assert "EXPECTED" in text, f"{command} {args}: no expected-form guidance"


def test_help_documents_every_dispatchable_command(state: WorkbenchState):
    """The command reference and the dispatch table cannot drift apart."""
    documented = {name.split()[0] for _, commands in COMMAND_GROUPS for name, _ in commands}
    dispatchable = {
        "help", "scenario", "status", "candidates", "decide", "select",
        "predict", "explore", "observe", "history", "diagnostics", "quit",
    }
    assert documented == dispatchable
    text = dispatch(state, "help", [])
    for command in dispatchable:
        assert command in text


def test_empty_input_shows_the_command_reference(state: WorkbenchState):
    assert dispatch(state, "", []) == dispatch(state, "help", [])


# -- prompt and masthead ------------------------------------------------------------------------------


def test_prompt_carries_the_active_candidate(state: WorkbenchState):
    assert "01" not in format_prompt(state)
    dispatch(state, "select", ["1"])
    assert "01" in format_prompt(state)
    dispatch(state, "select", ["5"])
    assert "05" in format_prompt(state)


def test_masthead_is_rules_not_a_frame():
    """The masthead is deliberately not a panel -- the top of a session
    must be visually distinct from every view inside it."""
    lines = format_masthead().splitlines()
    assert lines[0].startswith(theme.HEAVY)
    assert lines[-1].startswith(theme.HEAVY)
    assert not any(theme._ANSI.sub("", line)[:1] in FRAME_STARTS for line in lines)


# -- colour degradation --------------------------------------------------------------------------------


def test_colour_is_disabled_by_default_off_a_terminal(state: WorkbenchState):
    theme.set_color(None)
    text = dispatch(state, "status", [])
    assert "\x1b[" not in text  # captured output is never a TTY


def test_no_color_env_var_is_respected(monkeypatch, state: WorkbenchState):
    theme.set_color(None)
    monkeypatch.setenv("WORKBENCH_FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    assert theme.color_enabled() is False


def test_layout_is_identical_with_and_without_colour(state: WorkbenchState):
    """Colour is decoration, never structure: every view must occupy the
    same lines at the same widths in both modes.

    Text is compared by WIDTH rather than byte-for-byte, because a
    filled badge deliberately substitutes `[ACTIVE]` for inverse video
    when colour is unavailable -- colour is never the only carrier of a
    state, so the monochrome mode needs its own glyph. The substitution
    is width-preserving, which is exactly what this asserts."""
    theme.set_color(False)
    plain = {name: text for name, text in _rendered_views(state)}

    with open(EXAMPLE_SCENARIO_PATH, encoding="utf-8") as f:
        config = json.load(f)
    colored_state = bootstrap_research_scenario(config, clock=_fixed_clock())
    theme.set_color(True)
    colored = {name: theme._ANSI.sub("", text) for name, text in _rendered_views(colored_state)}

    assert set(plain) == set(colored)
    for name in plain:
        plain_lines = plain[name].splitlines()
        colored_lines = colored[name].splitlines()
        assert len(plain_lines) == len(colored_lines), f"{name}: line count differs between colour modes"
        for a, b in zip(plain_lines, colored_lines):
            assert len(a) == len(b), f"{name}: width differs between colour modes:\n  {a!r}\n  {b!r}"


def test_badge_fallback_preserves_width_without_colour():
    """The monochrome substitution for a filled badge must not shift
    anything on its row."""
    theme.set_color(True)
    colored = theme.visible_len(theme.badge("active", filled=True))
    theme.set_color(False)
    plain = theme.visible_len(theme.badge("active", filled=True))
    assert colored == plain
    assert theme.badge("active", filled=True) == "[ACTIVE]"


# -- Phase 74: the scenario workspace -------------------------------------------------------------------


def test_scenario_view_describes_the_research_programme(state: WorkbenchState):
    """`scenario` answers "what am I operating?" without reading JSON or
    source: study, property, process, criterion, every formulation and
    every context, and how much of the space has been measured."""
    text = dispatch(state, "scenario", [])
    assert "RESEARCH PROGRAMME" in text
    assert "polymer tensile strength study" in text
    assert "tensile_strength >= 80.0" in text
    for formulation in ("baseline", "modified", "high_filler"):
        assert formulation in text
    for temperature in ("25 C", "80 C", "120 C"):
        assert temperature in text
    assert "MEASURED CELLS" in text and "0 of 9" in text


def test_scenario_view_tracks_measured_coverage(state: WorkbenchState):
    """Coverage is plain counting over real sample counts, and is never
    presented as progress toward a goal."""
    assert "0 of 9" in dispatch(state, "scenario", [])
    dispatch(state, "select", ["1"])
    dispatch(state, "observe", ["82"])
    assert "1 of 9" in dispatch(state, "scenario", [])
    dispatch(state, "observe", ["85"])
    assert "1 of 9" in dispatch(state, "scenario", [])  # same cell, still one measured
    dispatch(state, "select", ["2"])
    dispatch(state, "observe", ["70"])
    assert "2 of 9" in dispatch(state, "scenario", [])


def test_scenario_view_reports_absence_rather_than_failing():
    """A session built directly, with no scenario, says so."""
    from workbench.interaction import bootstrap_multi_candidate_scenario
    built = bootstrap_multi_candidate_scenario(clock=_fixed_clock())
    object.__setattr__(built, "scenario", None)
    text = dispatch(built, "scenario", [])
    assert "NO SCENARIO LOADED" in text
    assert "EXPECTED" in text


def test_status_reports_the_current_recommendation_without_selecting(state: WorkbenchState):
    """`status` surfaces what the optimizer currently recommends, and is
    explicit that seeing it is not acting on it."""
    text = dispatch(state, "status", [])
    assert "CURRENT RECOMMENDATION" in text
    assert "advisory only" in text
    assert "select " in text
    assert state.selected_candidate is None  # inspecting status selects nothing


def test_status_recommendation_does_not_overwrite_the_users_last_decide(state: WorkbenchState):
    """`status` uses a read-only evaluation, so it never clobbers what
    the user's own `decide` recorded."""
    dispatch(state, "decide", [])
    recorded = state.last_decision
    assert recorded is not None
    dispatch(state, "status", [])
    assert state.last_decision is recorded


def test_status_notes_when_the_recommendation_is_already_active(state: WorkbenchState):
    recommended_line = dispatch(state, "status", []).split("RECOMMENDED")[1].split("\n")[0]
    number = recommended_line.strip().split()[0]
    dispatch(state, "select", [number])
    assert "this is the active candidate" in dispatch(state, "status", [])


# -- Phase 80: aliases ----------------------------------------------------------------------------------


@pytest.mark.parametrize("alias, canonical", [("?", "help"), ("about", "scenario"), ("q", "quit")])
def test_aliases_resolve_to_their_canonical_command(state: WorkbenchState, alias, canonical):
    assert dispatch(state, alias, []) == dispatch(state, canonical, [])


def test_exit_and_quit_both_end_the_session(state: WorkbenchState):
    assert dispatch(state, "exit", []) == "__QUIT__"
    assert dispatch(state, "quit", []) == "__QUIT__"


# -- Phases 75/76/79: console density -------------------------------------------------------------------


def test_registry_marks_what_is_unknown(state: WorkbenchState):
    """WHAT IS UNKNOWN must be scannable, not inferred from a zero."""
    text = dispatch(state, "candidates", [])
    assert text.count("UNMEASURED") == 9
    assert "MEASURED" in text and "0 of 9" in text

    dispatch(state, "select", ["1"])
    dispatch(state, "observe", ["82"])
    text = dispatch(state, "candidates", [])
    assert text.count("UNMEASURED") == 8  # the measured candidate lost its marker
    assert "1 of 9" in text
    assert "8 carry no observation yet" in text


def test_decision_table_reports_samples_per_candidate(state: WorkbenchState):
    text = dispatch(state, "decide", [])
    assert "SAMPLES" in text and "UTILITY" in text and "STATUS" in text
    header = next(line for line in text.splitlines() if "CANDIDATE" in line and "UTILITY" in line)
    assert header.index("SAMPLES") < header.index("UTILITY") < header.index("STATUS")


def test_decision_recommendation_shows_the_inputs_behind_it(state: WorkbenchState):
    """The basis block reports the computational facts that produced the
    ranking -- never an invented scientific explanation."""
    dispatch(state, "select", ["1"])
    dispatch(state, "observe", ["82"])
    dispatch(state, "observe", ["91"])
    text = dispatch(state, "decide", [])
    for field in ("PREDICTION", "UNCERTAINTY", "SAMPLES", "INFORMATION", "UTILITY", "BASIS"):
        assert field in text
    assert "highest current utility" in text
    assert "NEXT HIGHEST" in text  # contrast value, both already computed by materials.optimization


def test_diagnostics_report_sample_counts_and_candidate_identity(state: WorkbenchState):
    """Diagnostics is telemetry: it names the candidate by id and shows
    the sample count either side of every transition."""
    dispatch(state, "select", ["1"])
    dispatch(state, "observe", ["82"])
    dispatch(state, "observe", ["91"])
    text = dispatch(state, "diagnostics", [])
    assert "candidate_id" in text
    assert "model_state_key" in text
    assert "samples t" in text and "samples t+1" in text


def test_history_stays_narrative_while_diagnostics_stays_technical(state: WorkbenchState):
    """Two views over one trajectory: history reads as chronology,
    diagnostics as telemetry. Neither duplicates the other's role."""
    dispatch(state, "select", ["1"])
    dispatch(state, "observe", ["82"])
    dispatch(state, "observe", ["91"])
    history = dispatch(state, "history", [])
    diagnostics = dispatch(state, "diagnostics", [])

    for technical in ("model_state_key", "candidate_id", "samples t"):
        assert technical not in history
        assert technical in diagnostics
    for narrative in ("predicted", "observed", "residual"):
        assert narrative in history
    # both describe the same two transitions and agree on the residual
    assert history.count("→") == diagnostics.count("→") == 2
    assert "+9.0" in history and "+9.0" in diagnostics  # 91 - 82
