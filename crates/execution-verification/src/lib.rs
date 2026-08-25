//! Verification semantics: what was asked, what was checked, what came back.
//!
//! # Why verification is not Boolean
//!
//! This is the design consequence Phase 126 was run to find, and it is
//! the reason this crate exists in Rust rather than as a Python
//! interface.
//!
//! Phase 126 §6 established that the three substrates do not agree about
//! what a proof covers:
//!
//! ```text
//! SP1        does not commit to its input at all. SP1Stdin is never
//!            hashed and never reaches verify_proof, which checks
//!            version, exit code and public-values digest only.
//! RISC Zero  has a ReceiptClaim.input field, but Input is an
//!            UNINHABITED type; the only value that can reach it is a
//!            host-DECLARED input_digest, and Receipt::verify requires
//!            that digest to be zero.
//! Nexus      genuinely binds it -- verify_expected() reconstructs the
//!            whole execution View, input memory included.
//! ```
//!
//! Now consider the obvious interface:
//!
//! ```text
//! fn verify(proof, expectation) -> bool
//! ```
//!
//! Given the same expectation carrying program, input and output, an SP1
//! backend returns `true` having checked program and output only; a
//! Nexus backend returns the identical `true` having also checked the
//! input. **The caller cannot tell them apart, and is entitled to
//! believe the stronger claim in both cases.**
//!
//! That is Phase 111's failure mode -- an unwarranted claim entering
//! through a gate that looks like it checked -- reintroduced *by the
//! abstraction itself*. `Result<(), Error>` fails identically: it carries
//! exactly one bit of the same information.
//!
//! So this crate holds two rules and everything else follows from them:
//!
//! 1. A result always reports [`VerificationCoverage`] -- what was
//!    actually checked -- never a bare verdict.
//! 2. A backend is never asked an expectation it cannot cover.
//!    [`ProofBackend::verify`] screens against
//!    [`ProofBackend::capabilities`] first and returns
//!    [`VerificationResult::Unsupported`], so an uncheckable requirement
//!    cannot become a success by omission.

#![forbid(unsafe_code)]
#![deny(missing_docs)]
#![no_std]

extern crate alloc;

use alloc::vec::Vec;
use execution_model::{
    BackendId, InputIdentity, OutputIdentity, ProgramIdentity, ProofArtifact, ProofIdentity,
};

/// One thing a caller can require a verifier to check.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum RequiredCheck {
    /// That the proved execution ran THIS program.
    Program,
    /// That the proved execution ran on THIS input.
    ///
    /// Requiring this is the strong ask. Per
    /// [`execution_model::INPUT_COMMITMENT_INVARIANT`], a backend may
    /// only claim to have checked it if the proved execution itself
    /// binds the canonical [`InputIdentity`].
    Input,
    /// That the proved execution produced THIS output.
    Output,
    /// That the proved execution ended with THIS exit code.
    ExitCode,
}

/// What a caller requires of a verification.
///
/// The program is always required: a proof about an unspecified program
/// is not a claim about anything. Everything else is opt-in, and opting
/// in is what makes a backend that cannot deliver return
/// [`VerificationResult::Unsupported`] instead of a success.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Expectation {
    program: ProgramIdentity,
    input: Option<InputIdentity>,
    output: Option<OutputIdentity>,
    exit_code: Option<u32>,
}

impl Expectation {
    /// Require only that the proof is about this program.
    pub const fn of_program(program: ProgramIdentity) -> Self {
        Self {
            program,
            input: None,
            output: None,
            exit_code: None,
        }
    }

    /// Additionally require that the execution ran on this input.
    #[must_use]
    pub fn with_input(mut self, input: InputIdentity) -> Self {
        self.input = Some(input);
        self
    }

    /// Additionally require that the execution produced this output.
    #[must_use]
    pub fn with_output(mut self, output: OutputIdentity) -> Self {
        self.output = Some(output);
        self
    }

    /// Additionally require that the execution ended with this exit code.
    #[must_use]
    pub fn with_exit_code(mut self, exit_code: u32) -> Self {
        self.exit_code = Some(exit_code);
        self
    }

    /// The required program.
    pub const fn program(&self) -> &ProgramIdentity {
        &self.program
    }

    /// The required input, if the caller required one.
    pub const fn input(&self) -> Option<&InputIdentity> {
        self.input.as_ref()
    }

    /// The required output, if the caller required one.
    pub const fn output(&self) -> Option<&OutputIdentity> {
        self.output.as_ref()
    }

    /// The required exit code, if the caller required one.
    pub const fn exit_code(&self) -> Option<u32> {
        self.exit_code
    }

    /// Everything this expectation requires a verifier to check.
    pub fn required_checks(&self) -> Vec<RequiredCheck> {
        let mut checks = alloc::vec![RequiredCheck::Program];
        if self.input.is_some() {
            checks.push(RequiredCheck::Input);
        }
        if self.output.is_some() {
            checks.push(RequiredCheck::Output);
        }
        if self.exit_code.is_some() {
            checks.push(RequiredCheck::ExitCode);
        }
        checks
    }
}

/// What a verification ACTUALLY checked -- or what a backend is capable
/// of checking.
///
/// Four independent facts, deliberately not reducible to one. There is
/// no `is_complete() -> bool` and no `From<VerificationCoverage> for
/// bool`, because either would restore exactly the collapse this type
/// exists to prevent.
///
/// A coverage of
///
/// ```text
/// { program: true, input: false, output: true, exit_code: true }
/// ```
///
/// is a real and useful result. It is NOT complete verification, and it
/// must never be presented as such: it is consistent with the execution
/// having run on an input nobody checked.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct VerificationCoverage {
    /// The proved execution was checked to be of the expected program.
    pub program_checked: bool,
    /// The proved execution was checked to have run on the expected input.
    pub input_checked: bool,
    /// The proved execution was checked to have produced the expected output.
    pub output_checked: bool,
    /// The proved execution was checked to have ended with the expected exit code.
    pub exit_code_checked: bool,
}

impl VerificationCoverage {
    /// Nothing was checked. The only safe starting point, and the
    /// capability of any backend that cannot verify anything.
    pub const NONE: Self = Self {
        program_checked: false,
        input_checked: false,
        output_checked: false,
        exit_code_checked: false,
    };

    /// All four were checked.
    ///
    /// Named so that "complete" has to be written out by whoever claims
    /// it, and so tests can state the distinction from a partial coverage
    /// explicitly.
    pub const COMPLETE: Self = Self {
        program_checked: true,
        input_checked: true,
        output_checked: true,
        exit_code_checked: true,
    };

    /// Whether this coverage includes one particular check.
    pub const fn includes(&self, check: RequiredCheck) -> bool {
        match check {
            RequiredCheck::Program => self.program_checked,
            RequiredCheck::Input => self.input_checked,
            RequiredCheck::Output => self.output_checked,
            RequiredCheck::ExitCode => self.exit_code_checked,
        }
    }

    /// Which of `expectation`'s required checks this coverage does NOT
    /// include. Empty means the expectation is fully covered.
    pub fn missing(&self, expectation: &Expectation) -> Vec<RequiredCheck> {
        expectation
            .required_checks()
            .into_iter()
            .filter(|check| !self.includes(*check))
            .collect()
    }
}

impl Default for VerificationCoverage {
    /// [`VerificationCoverage::NONE`]. A default that assumed anything
    /// had been checked would be a fabricated warrant with a derive
    /// macro in front of it.
    fn default() -> Self {
        Self::NONE
    }
}

/// Why a verification failed.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum VerificationFailure {
    /// The proof is not about the expected program.
    ProgramMismatch,
    /// The proved execution did not run on the expected input.
    InputMismatch,
    /// The proved execution did not produce the expected output.
    OutputMismatch,
    /// The proved execution did not end with the expected exit code.
    ExitCodeMismatch,
    /// The proof itself did not verify.
    InvalidProof,
    /// The proof was produced by a version this verifier cannot check.
    ///
    /// Not an edge case: SP1's own verifier hard-fails on version
    /// mismatch (Phase 126 §8). A proof is verifiable by a compatible
    /// verifier, not forever.
    VersionMismatch {
        /// The version this verifier can check.
        expected: BackendId,
        /// The version the proof was produced under.
        found: BackendId,
    },
    /// The proof bytes could not be interpreted by this backend.
    Malformed,
}

/// The outcome of asking a backend to verify a proof against an
/// expectation.
///
/// Every variant carries coverage. Even a failure says what was
/// examined, because "it failed" and "it failed the one thing we could
/// check" are different facts.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum VerificationResult {
    /// The proof verified, and covered everything the expectation
    /// required.
    ///
    /// `coverage` is still reported and is still not necessarily
    /// [`VerificationCoverage::COMPLETE`] -- it is complete with respect
    /// to what was ASKED. A caller that asked only about the program
    /// gets a `Verified` whose `input_checked` is false, and that is
    /// correct and must stay visible.
    Verified {
        /// What was actually checked.
        coverage: VerificationCoverage,
        /// The proof that was checked.
        proof: ProofIdentity,
        /// The backend that checked it, and at what version.
        backend: BackendId,
    },
    /// The proof did not verify.
    Failed {
        /// What was checked before the failure was reached.
        coverage: VerificationCoverage,
        /// Why it failed.
        failure: VerificationFailure,
        /// The backend that checked it.
        backend: BackendId,
    },
    /// The backend cannot check what was required, and did not try.
    ///
    /// This is the variant that stops an uncheckable requirement from
    /// silently becoming a success. An SP1 backend asked to confirm an
    /// input lands here -- not in `Verified` with `input_checked: false`.
    Unsupported {
        /// What this backend can check at all.
        capabilities: VerificationCoverage,
        /// The required checks it cannot perform.
        missing: Vec<RequiredCheck>,
        /// The backend that declined.
        backend: BackendId,
    },
}

/// A proving backend that can check a proof against an expectation.
///
/// Phase 128's SP1 and Nexus adapters implement exactly this and nothing
/// more. Note what is NOT in it: no serialization, no program-commitment
/// accessor, no proving. Phase 126 §10 found those cannot be shared, so
/// they are not in the shared trait.
pub trait ProofBackend {
    /// This backend's name and version.
    fn backend(&self) -> &BackendId;

    /// What this backend is capable of checking, at all, ever.
    ///
    /// Per Phase 126 this is genuinely different per backend, and an
    /// honest implementation says so:
    ///
    /// ```text
    /// SP1        input_checked: false   (SP1Stdin is never committed to)
    /// RISC Zero  input_checked: false   (Input is uninhabited; input_digest
    ///                                    is host-declared and must be zero)
    /// Nexus      input_checked: true    (verify_expected binds the input)
    /// ```
    ///
    /// A backend that reports a capability it does not have has
    /// fabricated a warrant, and no amount of downstream typing can
    /// recover from that.
    fn capabilities(&self) -> VerificationCoverage;

    /// The backend-specific check. Implementors write THIS.
    ///
    /// It is called only for expectations this backend's
    /// [`capabilities`](ProofBackend::capabilities) already cover, so an
    /// implementation never has to decide what to do about a requirement
    /// it cannot meet -- it will not be asked.
    fn verify_supported(
        &self,
        artifact: &ProofArtifact,
        expectation: &Expectation,
    ) -> VerificationResult;

    /// The entry point. Callers call THIS.
    ///
    /// Screens the expectation against declared capabilities before the
    /// backend sees it. This is why "unsupported expectations cannot
    /// silently become success" is a structural property here rather
    /// than a convention every adapter must remember.
    fn verify(&self, artifact: &ProofArtifact, expectation: &Expectation) -> VerificationResult {
        let capabilities = self.capabilities();
        let missing = capabilities.missing(expectation);
        if !missing.is_empty() {
            return VerificationResult::Unsupported {
                capabilities,
                missing,
                backend: self.backend().clone(),
            };
        }
        self.verify_supported(artifact, expectation)
    }
}
