//! The reference workload: an integer pairwise inverse-power energy
//! kernel.
//!
//! ONE deterministic scientific-computing-shaped workload, chosen to be
//! the smallest thing that exercises the substrate's semantics with a
//! structure relevant to the eventual materials/simulation system: a set
//! of particle positions in, a pairwise-interaction scalar out.
//!
//! # What this is not
//!
//! It is NOT a materials primitive, NOT physically parameterised, NOT
//! admissible anywhere, and asserts nothing about any material. It is
//! Lennard-Jones-SHAPED -- a repulsive short-range term minus an
//! attractive long-range term -- because that shape exercises pairwise
//! iteration and accumulation, not because its constants mean anything.
//! `materials/` remains the only place scientific mathematics lives;
//! this kernel lives here so the substrate has one honest workload to
//! demonstrate identity semantics against.
//!
//! # Why integers
//!
//! The whole kernel is integer arithmetic (`i128` accumulation, integer
//! division truncating toward zero). Floating point would make
//! "deterministic" contingent on FMA contraction, x87 vs SSE, and libm
//! versions; integers make it a property. Determinism here is exercised
//! by tests, not promised by prose.
//!
//! # Exact semantics (these ARE the program, and the canonical
//! descriptor commits to them)
//!
//! ```text
//! input   := N * 12 bytes; each 12 bytes = x, y, z as i32 little-endian
//! bounds  := every coordinate must satisfy |c| <= 2^20        (else fault 4)
//! shape   := input length must be a multiple of 12            (else fault 2)
//! pairs   := for every i < j:
//!              r2 = (xi-xj)^2 + (yi-yj)^2 + (zi-zj)^2   in i128
//!              r2 == 0 is a fault                             (fault 3)
//!              e  = 2^80 / r2^2  -  2^40 / r2           integer division
//! output  := sum of e over all pairs, as i128 little-endian (16 bytes)
//! exit    := 0
//! ```
//!
//! Coincident particles fault rather than contributing anything: an
//! undefined term is refused, never replaced with a zero.

use crate::{DeterministicProgram, NativeCompletion, NativeFault};

/// The canonical descriptor [`PairwiseEnergyKernel`] is identified by.
///
/// It spells out the exact integer semantics above, so two kernels that
/// compute different things cannot honestly share it -- and so a future
/// guest implementation of the SAME semantics inside a zkVM can carry
/// the SAME descriptor and therefore the same `ProgramIdentity`.
pub const PAIRWISE_ENERGY_DESCRIPTOR: &[u8] = concat!(
    "scout.native.pairwise-energy-kernel.v1
",
    "input: N*12 bytes of (x,y,z) as i32 LE; |coord| <= 2^20
",
    "for i<j: r2=(dx^2+dy^2+dz^2) as i128; r2==0 faults;
",
    "e = 2^80/r2^2 - 2^40/r2 (integer division, truncation toward zero)
",
    "output: sum(e) as i128 LE (16 bytes); exit 0
",
    "faults: 2=malformed length, 3=coincident particles, 4=coordinate bound",
)
.as_bytes();

/// The reference workload. See the module documentation for exactly
/// what it computes and exactly what it does not claim.
pub struct PairwiseEnergyKernel;

impl DeterministicProgram for PairwiseEnergyKernel {
    fn canonical_bytes(&self) -> &[u8] {
        PAIRWISE_ENERGY_DESCRIPTOR
    }

    fn run(&self, input: &[u8]) -> Result<NativeCompletion, NativeFault> {
        // STE stage 2: the math moved to `execution-kernel` (no_std,
        // allocation-free) so the SP1 guest runs the SAME implementation
        // this backend does -- one function, two substrates. Behavior,
        // fault codes, check order and output bytes are unchanged, so
        // every identity is unchanged.
        match execution_kernel::pairwise_energy(input) {
            Ok(output) => Ok(NativeCompletion {
                output: output.to_vec(),
                exit_code: 0,
            }),
            Err(fault) => Err(NativeFault {
                exit_code: fault.exit_code,
                detail: fault.detail.to_string(),
            }),
        }
    }
}

/// Encode particle positions into the kernel's canonical input bytes.
///
/// This is the caller-side half of the canonicalization burden the Phase
/// 128 review named: the kernel identifies its input by BYTES, so a
/// caller that wants "the same particles -> the same InputIdentity" must
/// encode them the same way every time. This function is that one way.
pub fn encode_positions(positions: &[(i32, i32, i32)]) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(positions.len() * 12);
    for (x, y, z) in positions {
        bytes.extend_from_slice(&x.to_le_bytes());
        bytes.extend_from_slice(&y.to_le_bytes());
        bytes.extend_from_slice(&z.to_le_bytes());
    }
    bytes
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn determinism_same_bytes_same_energy() {
        let input = encode_positions(&[(0, 0, 0), (4, 0, 0), (0, 7, 0)]);
        let kernel = PairwiseEnergyKernel;
        assert_eq!(kernel.run(&input), kernel.run(&input));
    }

    #[test]
    fn energy_depends_on_geometry() {
        let kernel = PairwiseEnergyKernel;
        let near = kernel
            .run(&encode_positions(&[(0, 0, 0), (2, 0, 0)]))
            .unwrap();
        let far = kernel
            .run(&encode_positions(&[(0, 0, 0), (100, 0, 0)]))
            .unwrap();
        assert_ne!(near.output, far.output);
    }

    #[test]
    fn malformed_length_faults_with_code_2() {
        let fault = PairwiseEnergyKernel.run(&[1, 2, 3]).unwrap_err();
        assert_eq!(fault.exit_code, 2);
    }

    #[test]
    fn coincident_particles_fault_rather_than_contribute_zero() {
        let input = encode_positions(&[(5, 5, 5), (5, 5, 5)]);
        let fault = PairwiseEnergyKernel.run(&input).unwrap_err();
        assert_eq!(fault.exit_code, 3);
    }

    #[test]
    fn out_of_bounds_coordinate_faults_with_code_4() {
        let input = encode_positions(&[(0, 0, 0), (1 << 21, 0, 0)]);
        let fault = PairwiseEnergyKernel.run(&input).unwrap_err();
        assert_eq!(fault.exit_code, 4);
    }

    #[test]
    fn empty_and_single_particle_complete_with_zero_pairs() {
        // Zero pairs is a REAL result (there is nothing to sum), not an
        // unknown one -- so this completes with an output, unlike the
        // faults above which complete with none.
        let kernel = PairwiseEnergyKernel;
        let none = kernel.run(&[]).unwrap();
        let one = kernel.run(&encode_positions(&[(3, 3, 3)])).unwrap();
        assert_eq!(none.output, 0i128.to_le_bytes().to_vec());
        assert_eq!(one.output, 0i128.to_le_bytes().to_vec());
    }
}
