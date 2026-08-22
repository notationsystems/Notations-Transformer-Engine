"""EvidencePool: idempotent puts, non-deletion, conflict coexistence,
serialization/round-trip."""

from evidence.identity import canonical_json_bytes
from evidence.pool import EvidencePool
from evidence.types import make_claimed_relationship, make_document, make_observation, make_record, make_referent, make_source


def _seeded_pool():
    pool = EvidencePool()
    source = make_source(kind="paper", name="X")
    pool.put_source(source)
    document = make_document(source_id=source.id, raw_content="body", retrieval_method="fixture", retrieved_at="t")
    pool.put_document(document)
    record = make_record(document_id=document.id, locator="p1", raw_content="body")
    pool.put_record(record)
    return pool, source, document, record


def test_duplicate_put_is_idempotent():
    pool, source, document, record = _seeded_pool()
    size_before = len(pool)
    pool.put_source(source)
    pool.put_document(document)
    pool.put_record(record)
    assert len(pool) == size_before


def test_pool_never_loses_conflicting_observations():
    """Two different sources reporting different values for the same
    thing must both survive in the pool, unmodified -- §E's conflict
    model, exercised at the pool level."""
    pool, source, document, record = _seeded_pool()
    o1 = make_observation(
        record_ids=(record.id,), extraction_method="regex:kv_v1", content={"value": 1200}, confidence=1.0, extracted_at="t"
    )
    o2 = make_observation(
        record_ids=(record.id,), extraction_method="regex:kv_v1", content={"value": 1300}, confidence=1.0, extracted_at="t"
    )
    pool.put_observation(o1)
    pool.put_observation(o2)
    assert o1.id != o2.id
    stored = pool.all_observations()
    assert len(stored) == 2
    assert {o.id for o in stored} == {o1.id, o2.id}
    assert {dict(o.content)["value"] for o in stored} == {1200, 1300}


def test_observations_about_and_relationships_touching():
    pool, source, document, record = _seeded_pool()
    fep = make_referent(natural_key="FEP", kind="material")
    extrusion = make_referent(natural_key="extrusion", kind="process")
    pool.put_referent(fep)
    pool.put_referent(extrusion)
    obs = make_observation(
        record_ids=(record.id,), extraction_method="regex:kv_v1", content={"value": 1}, confidence=1.0, extracted_at="t"
    )
    pool.put_observation(obs)
    rel = make_claimed_relationship(
        from_referent_id=fep.id, to_referent_id=extrusion.id, type="used_in", observation_id=obs.id, confidence=1.0
    )
    pool.put_claimed_relationship(rel)

    assert pool.observations_about(fep.id) == (obs,)
    assert pool.relationships_touching(fep.id) == (rel,)
    assert pool.relationships_touching(extrusion.id) == (rel,)
    assert pool.observations_about("nonexistent") == ()


def test_pool_has_no_delete_method():
    """Non-deletion is structural, not just a convention: EvidencePool
    exposes no delete/remove method for any object type (§B: Document/
    Record/Observation/Referent/ClaimedRelationship are all "No" under
    "Deletable?")."""
    pool = EvidencePool()
    for name in dir(pool):
        assert "delete" not in name.lower() and "remove" not in name.lower(), (
            f"EvidencePool exposes {name!r} -- pool objects must never be deletable"
        )


def test_round_trip_content_hash_stable_for_serialized_observation():
    """An Observation's identity-defining payload survives a JSON
    round-trip unchanged -- the same discipline
    `core/canonical/version.py::canonical_json_bytes` already proves for
    CanonicalState, exercised here for Observation content."""
    import json

    obs = make_observation(
        record_ids=("r1", "r2"),
        extraction_method="regex:kv_v1",
        content={"value": 1250, "unit": "Pa.s"},
        confidence=1.0,
        extracted_at="t",
    )
    payload = {"record_ids": list(obs.record_ids), "extraction_method": obs.extraction_method, "content": dict(sorted(obs.content.items()))}
    round_tripped = json.loads(canonical_json_bytes(payload))
    assert round_tripped["content"] == dict(obs.content)
    assert round_tripped["record_ids"] == list(obs.record_ids)
