"""Stage 3 -- Nexus as the second independent implementer, audited live.

Every proof here is a genuine Nexus stwo proof generated on this
machine's CPU. Skips (as an environment gap, never a pass) when the
nexus-host binary or the Nexus guest ELF is not built.

The file asks the same tamper questions the SP1 file asks -- and asserts
the ANSWERS differ where the substrates genuinely differ: SP1's
extract-style verifier names the mismatched dimension (InputMismatch /
OutputMismatch / ExitCodeMismatch); Nexus's confirm-style verifier can
only report that the claimed statement is not the proven one
(StatementMismatch). Recording that asymmetry is part of the audit, not
a defect to hide.

Fork revision under test: nexus-zkvm f2ad126 (workspace 0.3.6),
stwo prover, guest target riscv32im-unknown-none-elf,
toolchain nightly-2025-05-09.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from execution.proving import (
    ProvedRunError,
    default_nexus_guest_elf_path,
    default_nexus_host_path,
    prove_and_verify,
)
from execution.specification import (
    PAIRWISE_ENERGY_DESCRIPTOR,
    ExecutionSpecification,
    encode_positions,
)

HOST = default_nexus_host_path()
ELF = default_nexus_guest_elf_path()

pytestmark = pytest.mark.skipif(
    not (HOST.exists() and ELF.exists()),
    reason="nexus-host or Nexus guest ELF not built (zk/nexus workspace + "
    "nightly-2025-05-09); environment gap, not an architectural pass",
)

#: The identical argon-pair geometry the SP1 proof covers.
ARGON_PAIR = [(1000, 1000, 1000), (1400, 1000, 1000)]


def _spec(positions=None) -> ExecutionSpecification:
    return ExecutionSpecification(
        program=PAIRWISE_ENERGY_DESCRIPTOR,
        configuration=b"",
        input_payload=encode_positions(positions or ARGON_PAIR),
    )


@pytest.fixture(scope="module")
def proved(tmp_path_factory):
    """ONE real Nexus proof, through the identical backend-neutral
    driver the SP1 tests use -- only the two paths differ."""
    proof_dir = tmp_path_factory.mktemp("nexus-proofs")
    return prove_and_verify(
        _spec(), proof_dir / "argon-pair.nexus.proof", host_path=HOST, elf_path=ELF
    )


def _verify(proof_path, *, program_file=None, input_hex=None, output_hex=None, exit_code=None,
            proved_run=None):
    descriptor_file = proof_path.parent / "descriptor.bin"
    descriptor_file.write_bytes(PAIRWISE_ENERGY_DESCRIPTOR)
    native = proved_run.execution
    args = [
        str(HOST), "verify", str(ELF), str(descriptor_file), str(proof_path),
        program_file if program_file is not None else "registered",
        input_hex if input_hex is not None else native.specification.input_payload.hex(),
        output_hex if output_hex is not None else native.output.hex(),
        str(exit_code if exit_code is not None else native.exit_code),
    ]
    proc = subprocess.run(args, capture_output=True, timeout=600)
    assert proc.returncode == 0, proc.stderr.decode()
    fields = {}
    for line in proc.stdout.decode().splitlines()[1:]:
        key, _, value = line.partition(" ")
        fields[key] = value
    return fields


# -- the contract, implemented a second time ----------------------------------------------------------


def test_the_full_chain_agrees_on_nexus(proved):
    """Native run, Nexus stwo proof, independent verification through
    the SAME sealed entry point and the SAME Python driver -- with the
    guest's in-circuit commitments equal to this layer's recomputations."""
    assert proved.execution.status == "completed"
    assert proved.backend_name == "nexus-stwo"
    assert proved.backend_version == "0.3.6@f2ad126"
    assert len(proved.proof_identity) == 64
    assert pathlib.Path(proved.proof_path).stat().st_size > 0


def test_verification_is_reproducible_from_the_artifact(proved):
    fields = _verify(pathlib.Path(proved.proof_path), proved_run=proved)
    assert fields["outcome"] == "verified"
    assert fields["coverage"] == "program=true input=true output=true exit_code=true"


# -- tampering: same questions, honestly different answers --------------------------------------------


def test_altered_input_is_rejected_as_statement_mismatch(proved):
    tampered = encode_positions([(1001, 1000, 1000), (1400, 1000, 1000)])
    fields = _verify(pathlib.Path(proved.proof_path), input_hex=tampered.hex(), proved_run=proved)
    assert fields["outcome"] == "failed"
    # Confirm-style: the mismatch is real but unattributable to the
    # input dimension specifically. StatementMismatch is the honest
    # answer; an InputMismatch here would be manufactured precision.
    assert "StatementMismatch" in fields["failure"]


def test_altered_program_identity_is_rejected_attributably(proved, tmp_path):
    """Program mismatch IS attributable on Nexus -- the binding check is
    the adapter's own, before the aggregate confirmation."""
    other_program = tmp_path / "other-program.bin"
    other_program.write_bytes(b"a different program's canonical bytes")
    fields = _verify(
        pathlib.Path(proved.proof_path), program_file=str(other_program), proved_run=proved
    )
    assert fields["outcome"] == "failed"
    assert "ProgramMismatch" in fields["failure"]


def test_altered_output_is_rejected_as_statement_mismatch(proved):
    tampered_output = bytes(reversed(proved.execution.output)).hex()
    fields = _verify(pathlib.Path(proved.proof_path), output_hex=tampered_output, proved_run=proved)
    assert fields["outcome"] == "failed"
    assert "StatementMismatch" in fields["failure"]


def test_altered_exit_code_is_rejected_as_statement_mismatch(proved):
    fields = _verify(pathlib.Path(proved.proof_path), exit_code=3, proved_run=proved)
    assert fields["outcome"] == "failed"
    assert "StatementMismatch" in fields["failure"]


def test_corrupted_proof_bytes_are_rejected(proved, tmp_path):
    corrupted = tmp_path / "corrupted.nexus.proof"
    raw = bytearray(pathlib.Path(proved.proof_path).read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    corrupted.write_bytes(bytes(raw))
    fields = _verify(corrupted, proved_run=proved)
    assert fields["outcome"] == "failed"
    assert ("StatementMismatch" in fields["failure"]) or ("Malformed" in fields["failure"])


def test_a_wrong_program_specification_is_refused_before_proving(tmp_path):
    foreign = ExecutionSpecification(
        program=b"not the registered guest", configuration=b"", input_payload=b""
    )
    with pytest.raises(ProvedRunError, match="not registered"):
        prove_and_verify(
            foreign, tmp_path / "never.proof", host_path=HOST, elf_path=ELF
        )
