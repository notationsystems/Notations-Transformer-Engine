"""prove_and_verify: the proved path -- `Verified` as an earned property.

The flow, per specification, with every arrow independently checked:

    ExecutionSpecification
        -> native execution        (run_specification: checked engine)
        -> SP1 proof               (sp1-host prove: real CPU proof, no
                                    mock path exists in the adapter)
        -> independent verification(sp1-host verify: the sealed
                                    ProofBackend::verify entry point)
        -> ProvedRun               (exists ONLY if everything agreed)

HARD FAILURE, BY CONSTRUCTION (requirement 8): there is no
`verified: bool` anywhere in this module. A mismatch between the guest's
committed input/output commitments and this layer's own recomputation, a
halted guest, a non-`verified` outcome, a missing artifact -- each raises
`ProvedRunError`, and the exception propagates through the dispatch seam
exactly like any dispatch failure: the operation ledger records FAILED
and nothing reaches the evidence path. A `ProvedRun` that exists is one
whose every check passed; a weaker one is unrepresentable.

WHAT A ProvedRun DOES NOT CLAIM: that anything was measured. The proof
establishes that the registered guest program read bytes with THIS input
commitment and produced bytes with THIS output commitment under SP1
semantics. Whether those input bytes describe the world is exactly as
unknowable as it was in Phase 111b.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from execution.engine import ExecutionResult, run_specification
from execution.specification import PAIRWISE_ENERGY_DESCRIPTOR, ExecutionSpecification

_REPO = pathlib.Path(__file__).resolve().parent.parent


class ProvingUnavailable(RuntimeError):
    """The prover binary or guest ELF is not built in this environment.
    An environment gap -- never reported as a verification outcome."""


class ProvedRunError(RuntimeError):
    """The hard failure. Anything short of full agreement lands here."""


def default_host_path() -> pathlib.Path:
    """Where the zk workspace builds the sp1-host binary."""
    return _REPO / "zk" / "target" / "release" / "sp1-host"


def default_guest_elf_path() -> pathlib.Path:
    """Where the succinct toolchain builds the guest ELF."""
    return (
        _REPO / "zk" / "guest-pairwise" / "target"
        / "riscv64im-succinct-zkvm-elf" / "release" / "ste-guest-pairwise"
    )


@dataclass(frozen=True)
class ProvedRun:
    """One execution that was natively run, proven, and independently
    verified -- all in agreement. Every field is data ABOUT the
    verification; none of them is a knob."""

    execution: ExecutionResult
    proof_path: str
    proof_identity: str
    backend_name: str
    backend_version: str
    vkey_hash: str


def _parse(stdout: str) -> dict:
    lines = stdout.splitlines()
    if not lines or lines[0] != "sp1-host-result v1":
        raise ProvedRunError(f"unrecognised sp1-host output: {lines[:1]!r}")
    fields = {}
    for line in lines[1:]:
        key, _, value = line.partition(" ")
        fields[key] = value
    return fields


def _run_host(host: pathlib.Path, args: list[str], timeout: int) -> dict:
    proc = subprocess.run([str(host), *args], capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise ProvedRunError(
            f"sp1-host exited {proc.returncode}: {proc.stderr.decode(errors='replace')[-400:]}"
        )
    return _parse(proc.stdout.decode())


def prove_and_verify(
    spec: ExecutionSpecification,
    proof_out: pathlib.Path,
    host_path: Optional[pathlib.Path] = None,
    elf_path: Optional[pathlib.Path] = None,
    prove_timeout: int = 3600,
) -> ProvedRun:
    """The whole chain, or an exception. See the module docstring."""
    host = host_path if host_path is not None else default_host_path()
    elf = elf_path if elf_path is not None else default_guest_elf_path()
    if not host.exists() or not elf.exists():
        raise ProvingUnavailable(
            f"sp1-host ({host}) or guest ELF ({elf}) not built; see zk/README notes "
            f"in docs/STE_VERIFICATION_SUBSTRATE.md"
        )
    if spec.program != PAIRWISE_ENERGY_DESCRIPTOR:
        raise ProvedRunError(
            "the SP1 adapter is bound to the pairwise-energy descriptor; refusing to "
            "prove a specification for a program the guest is not registered as"
        )

    # 1. The checked native execution.
    native = run_specification(spec)
    if native.status != "completed":
        raise ProvedRunError(
            f"native execution halted (exit {native.exit_code}); a run with no output "
            f"has nothing to prove in this stage"
        )

    with tempfile.TemporaryDirectory() as tmp:
        descriptor_file = pathlib.Path(tmp) / "descriptor.bin"
        descriptor_file.write_bytes(spec.program)

        # 2. Prove (the host verifies the fresh proof before reporting).
        prove = _run_host(
            host,
            ["prove", str(elf), str(descriptor_file), spec.input_payload.hex(), str(proof_out)],
            timeout=prove_timeout,
        )
        if prove.get("guest_status") != "completed":
            raise ProvedRunError(f"guest halted inside the zkVM: {prove}")

        # 3. Requirement 7 -- the host-side recomputation. The guest's
        # committed commitments must equal OUR canonical commitments over
        # bytes this layer already holds. Any drift between the two
        # implementations of the commitment function, any tampering with
        # the input en route, any disagreement between native and guest
        # kernels -- all land here.
        if prove.get("input_commitment") != native.input_identity:
            raise ProvedRunError(
                f"guest committed input {prove.get('input_commitment')}; "
                f"this layer computed {native.input_identity}"
            )
        if prove.get("output_commitment") != native.output_identity:
            raise ProvedRunError(
                f"guest committed output {prove.get('output_commitment')}; native "
                f"execution of the same kernel produced {native.output_identity}"
            )
        if int(prove.get("exit_code", "-1")) != native.exit_code:
            raise ProvedRunError(
                f"guest exit code {prove.get('exit_code')} != native {native.exit_code}"
            )

        # 4. Independent verification through the sealed entry point.
        verify = _run_host(
            host,
            [
                "verify", str(elf), str(descriptor_file), str(proof_out), "registered",
                spec.input_payload.hex(),
                (native.output or b"").hex(),
                str(native.exit_code),
            ],
            timeout=600,
        )
        if verify.get("outcome") != "verified":
            raise ProvedRunError(
                f"verification did not succeed: outcome={verify.get('outcome')} "
                f"failure={verify.get('failure')}"
            )
        backend_name, _, backend_version = verify.get("backend", " ").partition(" ")

    return ProvedRun(
        execution=native,
        proof_path=str(proof_out),
        proof_identity=verify["proof_identity"],
        backend_name=backend_name,
        backend_version=backend_version,
        vkey_hash=prove.get("vkey_hash", ""),
    )


def proved_runner(
    proof_dir: pathlib.Path,
    host_path: Optional[pathlib.Path] = None,
    elf_path: Optional[pathlib.Path] = None,
) -> Callable[[ExecutionSpecification], ExecutionResult]:
    """A runner for `SpecificationDispatcher` on which every dispatched
    computation must be proven and verified before its result proceeds.

    A verification failure raises out of `dispatch` -- the Phase 125 seam
    records FAILED, nothing is admitted, and there is no flag to check
    and no way to forget to check it (requirement 8)."""

    def run(spec: ExecutionSpecification) -> ExecutionResult:
        proof_out = proof_dir / f"proof-{spec.identity()[:16]}.bin"
        proved = prove_and_verify(spec, proof_out, host_path=host_path, elf_path=elf_path)
        return proved.execution

    return run
