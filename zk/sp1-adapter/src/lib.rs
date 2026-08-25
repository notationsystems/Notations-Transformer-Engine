//! The SP1 adapter: the first backend for which `Verified` is EARNED.
//!
//! Implements `execution_core::ProofBackend` over the SP1 fork's CPU
//! prover/verifier for exactly one guest: `ste-guest-pairwise`, the
//! pairwise-energy kernel compiled to riscv64im-succinct-zkvm-elf,
//! carrying the guest-input-commitment convention
//! (`ste.sp1.pairwise-io.v1`).
//!
//! # What a verified proof from this adapter establishes
//!
//! Assuming SP1 circuit soundness at the verifier's version:
//!
//!   1. The RISC-V program whose verifying key this adapter holds
//!      executed under SP1 semantics.                         [program*]
//!   2. That execution READ input bytes whose canonical commitment
//!      (SHA-256 under `scout.execution.input.v1`, computed INSIDE the
//!      proved execution by the same `execution-commitment` crate the
//!      host uses) is the one in the public values.           [input]
//!   3. It produced output bytes whose canonical commitment is the one
//!      in the public values, or halted with the committed fault code
//!      and NO output.                                        [output]
//!   4. It ended with the committed exit code.                [exit]
//!
//! [program*] carries one declared link, stated rather than hidden: the
//! proof binds the GUEST ELF (via its verifying key). The claim that
//! this ELF implements `PAIRWISE_ENERGY_DESCRIPTOR`'s semantics is a
//! BINDING registered at setup -- made credible by both substrates
//! compiling the identical `execution-kernel` function, and checked
//! empirically every proved run (native output must equal proved
//! output), but not itself proven. An `Expectation` naming any other
//! program identity is rejected as `ProgramMismatch`.
//!
//! # What it does NOT establish
//!
//! That the input corresponds to any physical event. A fabricated value
//! is computed -- and proved -- faithfully. Nothing produced here is
//! Evidence, nothing here touches the EvidencePool, and no field in any
//! type of this crate asserts measurement.
//!
//! # No mock path
//!
//! This adapter constructs the CPU prover explicitly. There is no code
//! path to SP1's mock prover from here: a `Verified` from this crate is
//! backed by a real proof or it does not exist.

use execution_core::{
    AdapterVerdict, BackendId, Expectation, ProgramIdentity, ProofArtifact, ProofBackend,
    VerificationCoverage, VerificationFailure,
};
use sp1_sdk::blocking::{CpuProver, ProveRequest, Prover, ProverClient};
use sp1_sdk::{Elf, HashableKey, ProvingKey, SP1ProofWithPublicValues, SP1ProvingKey, SP1Stdin};

/// The public-values layout tag. Must match the guest's constant.
pub const SP1_IO_CONVENTION_TAG: &[u8] = b"ste.sp1.pairwise-io.v1";

/// What the guest committed, parsed from the public values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommittedStatement {
    /// The guest-computed canonical input commitment (32 bytes hex).
    pub input_commitment_hex: String,
    /// The guest-computed canonical output commitment; `None` when the
    /// guest halted -- absence is a marker byte, never a zeroed digest.
    pub output_commitment_hex: Option<String>,
    /// The committed exit code (0, or the kernel fault code on halt).
    pub exit_code: u32,
}

/// Parse the `ste.sp1.pairwise-io.v1` public-values layout, strictly.
///
/// Anything off -- wrong tag, wrong marker, wrong length -- is `None`;
/// the caller reports `Malformed`. A layout that "almost parses" binds
/// nothing.
pub fn parse_committed_statement(public_values: &[u8]) -> Option<CommittedStatement> {
    let rest = public_values.strip_prefix(SP1_IO_CONVENTION_TAG)?;
    let (input_commitment, rest) = rest.split_at_checked(32)?;
    let (marker, rest) = rest.split_first()?;
    match marker {
        0 => {
            let (output_commitment, rest) = rest.split_at_checked(32)?;
            let exit: [u8; 4] = rest.try_into().ok()?;
            Some(CommittedStatement {
                input_commitment_hex: hex(input_commitment),
                output_commitment_hex: Some(hex(output_commitment)),
                exit_code: u32::from_le_bytes(exit),
            })
        }
        1 => {
            let exit: [u8; 4] = rest.try_into().ok()?;
            Some(CommittedStatement {
                input_commitment_hex: hex(input_commitment),
                output_commitment_hex: None,
                exit_code: u32::from_le_bytes(exit),
            })
        }
        _ => None,
    }
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// The SP1 backend for the pairwise-energy guest.
pub struct Sp1PairwiseBackend {
    client: CpuProver,
    pk: SP1ProvingKey,
    backend_id: BackendId,
    /// The descriptor-level program identity this guest is REGISTERED as
    /// implementing -- the declared binding described in the crate docs.
    program_binding: ProgramIdentity,
}

impl Sp1PairwiseBackend {
    /// Set up the CPU prover for `elf_bytes`, registering the binding to
    /// `program_binding` (the canonical descriptor's ProgramIdentity).
    pub fn setup(elf_bytes: Vec<u8>, program_binding: ProgramIdentity) -> anyhow::Result<Self> {
        let client = ProverClient::builder().cpu().build();
        let pk = client.setup(Elf::from(elf_bytes))?;
        let backend_id = BackendId::new("sp1-cpu", client.version());
        Ok(Self {
            client,
            pk,
            backend_id,
            program_binding,
        })
    }

    /// The verifying-key hash (`bytes32`) -- SP1's native program
    /// commitment for the guest ELF, reported BESIDE our identity and
    /// never as it.
    pub fn vkey_hash(&self) -> String {
        self.pk.verifying_key().vk.bytes32()
    }

    /// Execute + prove (core mode) the guest over `input`, then verify
    /// the fresh proof immediately. Returns the serialized proof bundle
    /// and the statement the guest committed.
    pub fn prove(&self, input: &[u8]) -> anyhow::Result<(Vec<u8>, CommittedStatement)> {
        let mut stdin = SP1Stdin::new();
        stdin.write_vec(input.to_vec());
        let proof = self.client.prove(&self.pk, stdin).core().run()?;
        // Verify immediately: a proof this adapter cannot verify is not
        // handed to anyone.
        self.client.verify(&proof, self.pk.verifying_key(), None)?;
        let statement = parse_committed_statement(proof.public_values.as_slice())
            .ok_or_else(|| anyhow::anyhow!("guest committed an unparseable statement"))?;
        Ok((bincode::serialize(&proof)?, statement))
    }
}

impl ProofBackend for Sp1PairwiseBackend {
    fn backend(&self) -> &BackendId {
        &self.backend_id
    }

    /// All four -- and each is a claim with a mechanism, not an
    /// aspiration: program via the verifying key (plus the declared
    /// descriptor binding, see crate docs), input via the guest
    /// convention (the recon's `input_checked: false` for SP1 was about
    /// the SUBSTRATE; the guest convention is exactly the construction
    /// Phase 126 identified as the only honest upgrade), output and exit
    /// code via the committed public values.
    fn capabilities(&self) -> VerificationCoverage {
        VerificationCoverage::COMPLETE
    }

    fn verify_supported(
        &self,
        artifact: &ProofArtifact,
        expectation: &Expectation,
    ) -> AdapterVerdict {
        let mut coverage = VerificationCoverage::NONE;

        let Ok(proof) = bincode::deserialize::<SP1ProofWithPublicValues>(artifact.bytes()) else {
            return AdapterVerdict::Reject {
                coverage,
                failure: VerificationFailure::Malformed,
            };
        };

        // The cryptographic check: the SDK's real verifier, which also
        // hard-fails on version mismatch (Phase 126 §8).
        if let Err(error) = self.client.verify(&proof, self.pk.verifying_key(), None) {
            let text = format!("{error:?}");
            let failure = if text.contains("VersionMismatch") {
                VerificationFailure::VersionMismatch {
                    expected: self.backend_id.clone(),
                    found: BackendId::new("sp1-cpu", proof.sp1_version.clone()),
                }
            } else {
                VerificationFailure::InvalidProof
            };
            return AdapterVerdict::Reject { coverage, failure };
        }

        let Some(statement) = parse_committed_statement(proof.public_values.as_slice()) else {
            return AdapterVerdict::Reject {
                coverage,
                failure: VerificationFailure::Malformed,
            };
        };

        // Program: the proof is bound to OUR verifying key (the SDK
        // verify above used self.pk); what remains is whether the caller
        // asked about the program this guest is registered as.
        coverage.program_checked = true;
        if expectation.program() != &self.program_binding {
            return AdapterVerdict::Reject {
                coverage,
                failure: VerificationFailure::ProgramMismatch,
            };
        }

        if let Some(expected_input) = expectation.input() {
            coverage.input_checked = true;
            if statement.input_commitment_hex != expected_input.to_hex() {
                return AdapterVerdict::Reject {
                    coverage,
                    failure: VerificationFailure::InputMismatch,
                };
            }
        }

        if let Some(expected_output) = expectation.output() {
            coverage.output_checked = true;
            match &statement.output_commitment_hex {
                Some(committed) if *committed == expected_output.to_hex() => {}
                // A halted execution committed NO output; it cannot
                // match any expected output, and saying so is the
                // mismatch, not a fabricated comparison against zeros.
                _ => {
                    return AdapterVerdict::Reject {
                        coverage,
                        failure: VerificationFailure::OutputMismatch,
                    };
                }
            }
        }

        if let Some(expected_exit) = expectation.exit_code() {
            coverage.exit_code_checked = true;
            if statement.exit_code != expected_exit {
                return AdapterVerdict::Reject {
                    coverage,
                    failure: VerificationFailure::ExitCodeMismatch,
                };
            }
        }

        // Coverage reports what was examined: exactly the required set.
        debug_assert!(coverage.missing(expectation).is_empty());
        AdapterVerdict::Accept { coverage }
    }
}
