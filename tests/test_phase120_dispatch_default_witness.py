"""Phase 120: DispatchedMeasurement default / witness boundary audit.

sec.7 VERDICT: B -- FALSIFIED.

The default asserts execution without a structural witness. It is the
SAME defect as Phase 119's in kind, smaller in reach, and worse in what
it has actually done.

sec.1 THE EXHAUSTIVE CONSTRUCTION AUDIT -- ONE SITE, AND IT IS A FIXTURE
-------------------------------------------------------------------------
An AST sweep of the entire repository finds EXACTLY ONE construction of
`DispatchedMeasurement`:

    tests/test_experiment_step.py:54   ScriptedDispatcher.dispatch

ZERO in production. And that one site OMITS `extraction_method`, so the
default fires. `ScriptedDispatcher`'s own docstring:

    "A deterministic, test/demo-oriented `ActionDispatcher` ... Returns a
     pre-scripted value per candidate_id; never touches EvidencePool,
     never reads a clock."

So THE ONLY OBJECT THAT HAS EVER TAKEN THIS DEFAULT IS A FIXTURE
RETURNING HARDCODED NUMBERS, AND THE DEFAULT DECLARES THEM A MEASUREMENT
PRODUCED BY CAMPAIGN EXECUTION. Its entire observed lifetime has been
mislabelling scripted constants.

Phase 119's removed default at least fired on real workbench observations
where a human had typed a number they had actually measured. This one has
never fired on anything but a test constant.

sec.4 THE NAME IS NOT A WITNESS
--------------------------------
The proposed justification -- "the object is called DispatchedMeasurement,
so it was dispatched" -- requires the type to be structurally tied to the
Protocol. It is not:

    no factory (`make_dispatched_measurement` does not exist)
    no admission gate
    no `__post_init__` validation of the method (it only freezes `content`)
    no restriction on construction

`ActionDispatcher` RETURNS the type; it does not OWN it. A bare
constructor call from anywhere yields
`extraction_method="measurement:campaign_execution"`. Nomenclature is not
provenance -- which is the same result Phase 117 reached for the field
itself and Phase 111b reached for the whole pool.

sec.2 FOUR WORLDS, ONE OBJECT
-------------------------------
A genuine instrument reading, a construction with nothing running, a
hand-fabricated value and a simulation output -- passed through the same
constructor with the same content -- produce FOUR EQUAL OBJECTS, all
declaring `measurement:campaign_execution`. The constructor cannot
distinguish them and does not try.

sec.5 THE COMPARISON WITH PHASE 119
-------------------------------------
Identical defect shape:

    absence of caller information -> positive assertion about a world event

The candidate difference was "construction context supplies a genuinely
different guarantee". Tested and rejected: the context is a Protocol
return type with no enforcement, and the sole construction site is a
fixture that is explicitly not a measurement.

The ONE genuine difference is REACH, not justification. `DispatchedMeasurement`
has no id, is never admitted, and nothing in production constructs it, so
the default currently causes no production harm. That is an accident of
the execution seam being empty (Phase 114: no `ActionDispatcher`
implementation exists and none is planned), NOT a structural guarantee.
An empty seam is not a witness either.

sec.3 THE DEFAULT-REMOVAL TEST, RUN AND REVERTED
--------------------------------------------------
Measured, not theorised. With `extraction_method: str` required:

    5 test failures, 1784 passing
      3 in tests/test_experiment_step.py  -- ScriptedDispatcher, one line
      2 locks asserting the default exists -- they did their job
    0 production callers break             -- there are none
    0 identities change                    -- the object has no id
    0 admission semantics change           -- it is never admitted
    0 legitimate callers lose information  -- the sole caller gains the
                                              obligation to say what it did

The change would MERELY RELOCATE A DECLARATION, exactly as Phase 119's
did -- with one difference worth stating plainly: the sole caller could
not honestly relocate `"measurement:campaign_execution"`, because
`ScriptedDispatcher` does not measure anything. It would have to declare
something true of a scripted fixture. That choice is a semantic decision
and is NOT made here.

sec.7 SMALLEST REPAIR, AND THE DISTINCTION IT MUST PRESERVE
-------------------------------------------------------------
    REPAIR OF SILENT ASSERTION
        make `DispatchedMeasurement.extraction_method` required, and have
        `ScriptedDispatcher` declare what it actually is. One signature
        line plus one fixture line. No new type, no gate, no factory.

    ESTABLISHMENT OF AUTHENTICITY
        NOT ATTEMPTED AND NOT ACHIEVABLE. Phase 119 proved that a
        required declaration leaves genuine, fabricated, simulated and
        hand-typed values collapsing to one identical Observation
        whenever the caller declares the same method. Requiring this
        declaration removes the architecture's unsolicited claim. It
        supplies no witness, and per Phase 111b none can be supplied from
        inside a content-addressed system.

WHY NOT (C) VACUOUS
--------------------
The C reading -- "no execution concept exists, so the question is
meaningless" -- was considered and rejected. The assertion is perfectly
meaningful and perfectly false: the string reaches
`classify_epistemic_status` and reaches `Observation.id` through
`run_experiment_step`, and it has determined the declared provenance of
every observation in this codebase's only end-to-end experiment test. It
is the JUSTIFICATION that is missing, not the meaning.

NO ABSTRACTION IS PROPOSED. Zero production changes in this phase.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

import pytest

from experiment.interface import ActionDispatcher, DispatchedMeasurement
from workbench import theme

REPO = Path(__file__).resolve().parent.parent
DEFAULT = "measurement:campaign_execution"
TIMESTAMP = "2026-01-01T00:00:00Z"
CONTENT = {"property": "tensile_strength", "value": 90.0, "unit": "MPa"}


@pytest.fixture(autouse=True)
def _plain():
    theme.set_color(False)
    yield
    theme.set_color(None)


def _construction_sites():
    sites = []
    for path in sorted(REPO.rglob("*.py")):
        if ".git" in str(path) or "notationsystems" in str(path):
            continue
        if path.name == Path(__file__).name:
            continue        # this audit's own probes construct one
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "id", None) == "DispatchedMeasurement"):
                sites.append((str(path.relative_to(REPO)), node.lineno,
                              "extraction_method" in {k.arg for k in node.keywords}))
    return sites


# -- 1. the exhaustive construction audit -------------------------------------------------------------


def test_exactly_one_construction_site_exists_and_it_is_a_test_fixture():
    sites = _construction_sites()
    assert len(sites) == 1
    path, _, declares = sites[0]
    assert path == "tests/test_experiment_step.py"
    assert declares is False          # it takes the default


def test_no_production_module_ever_constructs_one():
    production = [s for s in _construction_sites() if not s[0].startswith("tests/")]
    assert production == []


def test_the_sole_constructor_documents_itself_as_scripted_and_not_a_measurement():
    text = " ".join((REPO / "tests" / "test_experiment_step.py").read_text().split())
    assert "test/demo-oriented `ActionDispatcher`" in text
    assert "Returns a pre-scripted value per candidate_id" in text
    assert "never touches EvidencePool, never reads a clock" in text


# -- 4. the name is not a witness -----------------------------------------------------------------------


def test_the_type_is_freely_constructible_with_no_factory_or_gate():
    import experiment.interface as interface
    assert not hasattr(interface, "make_dispatched_measurement")
    public = {n for n in dir(interface) if not n.startswith("_")}
    assert "ActionDispatcher" in public and "DispatchedMeasurement" in public
    # a bare call from anywhere gets the claim for free
    bare = DispatchedMeasurement(content={"x": 1}, record_locator="l",
                                 record_raw_content="1", extracted_at=TIMESTAMP)
    assert bare.extraction_method == DEFAULT


def test_post_init_freezes_content_and_validates_nothing():
    source = inspect.getsource(DispatchedMeasurement)
    assert "MappingProxyType" in source
    for absent in ("raise", "ValueError", "assert"):
        assert absent not in source.split("__post_init__")[-1]


def test_the_protocol_returns_the_type_but_does_not_own_it():
    signature = inspect.signature(ActionDispatcher.dispatch)
    assert signature.return_annotation == "DispatchedMeasurement"
    # A Protocol return annotation constrains implementations, never
    # constructors: anyone may build one without implementing anything,
    # and nothing records which implementation (if any) produced it.
    assert "id" not in {f.name for f in dataclasses.fields(DispatchedMeasurement)}
    assert "dispatcher" not in {f.name for f in dataclasses.fields(DispatchedMeasurement)}


# -- 2. four worlds, one object ---------------------------------------------------------------------------


@pytest.mark.parametrize("world", [
    "genuine instrument reading",
    "constructed, nothing ran",
    "fabricated by hand",
    "simulation output",
])
def test_every_world_is_labelled_a_campaign_measurement(world):
    made = DispatchedMeasurement(content=CONTENT, record_locator="loadframe-run-7",
                                 record_raw_content="90.0", extracted_at=TIMESTAMP)
    assert made.extraction_method == DEFAULT, world


def test_the_four_worlds_are_equal_as_objects():
    made = [DispatchedMeasurement(content=CONTENT, record_locator="loadframe-run-7",
                                  record_raw_content="90.0", extracted_at=TIMESTAMP)
            for _ in range(4)]
    signatures = {(m.record_locator, m.record_raw_content, m.extraction_method,
                   tuple(sorted(m.content.items()))) for m in made}
    assert len(signatures) == 1


# -- 3. the measured blast radius --------------------------------------------------------------------------


def test_the_object_has_no_identity_so_removal_shifts_nothing_downstream():
    fields = {f.name for f in dataclasses.fields(DispatchedMeasurement)}
    assert "id" not in fields
    assert fields == {"content", "record_locator", "record_raw_content",
                      "extracted_at", "extraction_method"}


def test_it_is_never_admitted_and_reaches_no_pool_method():
    from evidence.pool import EvidencePool
    for absent in ("put_dispatched_measurement", "put_dispatch"):
        assert not hasattr(EvidencePool, absent)
    import evidence.admission as admission
    assert not any(n.endswith("dispatched_measurement") for n in dir(admission))


def test_only_the_extraction_method_is_read_downstream():
    from experiment.step import run_experiment_step
    source = inspect.getsource(run_experiment_step)
    reads = {node.attr for node in ast.walk(ast.parse(source.lstrip()))
             if isinstance(node, ast.Attribute)
             and isinstance(node.value, ast.Name) and node.value.id == "dispatched"}
    assert reads == {"record_locator", "record_raw_content", "content",
                     "extracted_at", "extraction_method"}
    # five fields copied, nothing retained -- Phase 118's payload-supplier
    # finding, re-confirmed.


# -- 5/7. the defect is the same shape as Phase 119's --------------------------------------------------------


def test_this_default_and_the_removed_one_have_the_same_shape():
    """absence of caller information -> positive assertion about a world
    event. The removed one is gone; this one remains."""
    from materials.results import make_experimental_result
    removed = inspect.signature(make_experimental_result).parameters["extraction_method"]
    assert removed.default is inspect.Parameter.empty          # Phase 119

    remaining = [f for f in dataclasses.fields(DispatchedMeasurement)
                 if f.name == "extraction_method"][0]
    assert remaining.default == DEFAULT                        # this phase


def test_the_default_stands_unrepaired_and_no_abstraction_is_proposed():
    """This phase reports. It does not repair, and it proposes nothing."""
    assert [f for f in dataclasses.fields(DispatchedMeasurement)
            if f.name == "extraction_method"][0].default == DEFAULT

    forbidden = {"ExecutionRecord", "MeasurementOrigin", "ProvenanceEvent",
                 "TrustedDispatcher", "Witness"}
    hits = []
    for package in ("evidence", "retrieval", "materials", "experiment",
                    "workbench", "scout"):
        root = REPO / package
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in forbidden:
                    hits.append(f"{path.relative_to(REPO)}: {node.name}")
    assert hits == [], hits
