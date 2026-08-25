"""ExecutionSpecification: the request to execute -- before any run.

WHAT PROPOSITION IT REPRESENTS: "run the program identified by these
canonical bytes, under this configuration, over this input." A request,
not an event: constructing one executes nothing, and its identity is a
content hash precisely because two identical requests ARE the same
request (asking twice is asking the same thing -- it is RUNNING twice
that must remain two, and that distinction belongs to the operation
ledgers, never to this type).

WHAT IT DOES NOT ESTABLISH: that the program bytes describe any real
behavior (that coupling is declared, not proven -- see
`native_program_identity_binds_bytes_not_behavior`), that the input was
measured, or that execution will be possible at all (the engine may
refuse: unknown program, unsupported configuration).

WHY THIS TYPE EXISTS NOW when the Phase 128 review rejected it: the
review rejected a specification identity FOR LACK OF A CONSUMER. The
consumer arrived with the cross-process boundary: a result coming back
from another process must name which request it answers, or it is the
detachable-warrant hazard (Phase 128 probe 1) at the process seam. The
reversal is recorded here and at `SPECIFICATION_TAG`'s definition in
`crates/execution-model`, not made silently.

IDENTITY: `commit(SPECIFICATION_TAG, [program, configuration, input])`.
Deliberately NOT part of it: any occurrence number, any timestamp, any
hostname, any engine version -- a request is the same request no matter
when, where, or how often it is made.
"""

from __future__ import annotations

from dataclasses import dataclass

from execution.commitments import (
    INPUT_TAG,
    PROGRAM_TAG,
    SPECIFICATION_TAG,
    commit_hex,
)

#: The reference workload's canonical descriptor -- byte-for-byte
#: `execution_native::reference::PAIRWISE_ENERGY_DESCRIPTOR`. The
#: round-trip test pins the agreement: if these bytes drift from the
#: Rust constant, the engine answers `unrunnable` and everything fails
#: loudly.
PAIRWISE_ENERGY_DESCRIPTOR = (
    b"scout.native.pairwise-energy-kernel.v1\n"
    b"input: N*12 bytes of (x,y,z) as i32 LE; |coord| <= 2^20\n"
    b"for i<j: r2=(dx^2+dy^2+dz^2) as i128; r2==0 faults;\n"
    b"e = 2^80/r2^2 - 2^40/r2 (integer division, truncation toward zero)\n"
    b"output: sum(e) as i128 LE (16 bytes); exit 0\n"
    b"faults: 2=malformed length, 3=coincident particles, 4=coordinate bound"
)


@dataclass(frozen=True)
class ExecutionSpecification:
    """See the module docstring -- it is this type's contract."""

    program: bytes
    configuration: bytes
    input_payload: bytes

    def identity(self) -> str:
        """The request's content identity (64 lowercase hex)."""
        return commit_hex(
            SPECIFICATION_TAG, [self.program, self.configuration, self.input_payload]
        )

    def program_identity(self) -> str:
        """Our commitment to the program bytes."""
        return commit_hex(PROGRAM_TAG, [self.program])

    def input_identity(self) -> str:
        """Our commitment to the input bytes.

        The canonicalization burden is the CALLER'S: this hashes the
        bytes it is given (Phase 128, probe 3). For the reference
        workload, `encode_positions` below is the one canonical
        encoding."""
        return commit_hex(INPUT_TAG, [self.input_payload])


def encode_positions(positions: list[tuple[int, int, int]]) -> bytes:
    """The reference workload's canonical input encoding -- mirrors
    `execution_native::reference::encode_positions` so the same particle
    list yields the same InputIdentity from either language."""
    import struct

    return b"".join(struct.pack("<iii", x, y, z) for (x, y, z) in positions)
