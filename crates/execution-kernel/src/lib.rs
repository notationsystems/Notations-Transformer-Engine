//! The pairwise-energy kernel's MATH, alone, `no_std`, allocation-free.
//!
//! Extracted from `execution-native` in STE stage 2 for one reason: the
//! same function must run in two places that cannot share `std` -- the
//! native backend (host) and the SP1 guest (RISC-V, `no_std`). One
//! implementation, two substrates, so native output and proved output
//! are outputs of the SAME code, not of two implementations claimed to
//! agree.
//!
//! The semantics are the ones `PAIRWISE_ENERGY_DESCRIPTOR` has committed
//! to since Phase 129 -- this refactor changes no behavior, no fault
//! code, no output byte, and therefore no identity. Check order is part
//! of those semantics and is preserved exactly: length first, then
//! per-particle coordinate bound during parse, then coincidence during
//! the pair loop.
//!
//! No allocation: positions are re-decoded by index, and the output is a
//! fixed 16-byte array -- which is also what makes this trivially
//! compilable for a zkVM guest.

#![forbid(unsafe_code)]
#![deny(missing_docs)]
#![no_std]

/// Fault: input length is not a multiple of 12.
pub const FAULT_MALFORMED_LENGTH: u32 = 2;
/// Fault: two particles are coincident (r2 == 0). An undefined term is
/// refused, never replaced with a zero.
pub const FAULT_COINCIDENT: u32 = 3;
/// Fault: a coordinate exceeds |c| <= 2^20.
pub const FAULT_COORDINATE_BOUND: u32 = 4;

const COORDINATE_BOUND: i32 = 1 << 20;
const REPULSIVE_NUMERATOR: i128 = 1 << 80;
const ATTRACTIVE_NUMERATOR: i128 = 1 << 40;

/// One fault: the exit code the descriptor assigns, plus a static
/// description (no formatting, no allocation).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct KernelFault {
    /// The descriptor's fault exit code (2, 3 or 4).
    pub exit_code: u32,
    /// A static human-readable description.
    pub detail: &'static str,
}

#[inline]
fn position(input: &[u8], index: usize) -> (i32, i32, i32) {
    let at = index * 12;
    let word = |offset: usize| {
        i32::from_le_bytes([
            input[at + offset],
            input[at + offset + 1],
            input[at + offset + 2],
            input[at + offset + 3],
        ])
    };
    (word(0), word(4), word(8))
}

/// Compute the pairwise inverse-power energy over `input`, exactly per
/// the descriptor. Returns the 16 output bytes (sum as i128 LE) or the
/// fault refusing the computation.
pub fn pairwise_energy(input: &[u8]) -> Result<[u8; 16], KernelFault> {
    if !input.len().is_multiple_of(12) {
        return Err(KernelFault {
            exit_code: FAULT_MALFORMED_LENGTH,
            detail: "input length is not a multiple of 12",
        });
    }
    let count = input.len() / 12;
    for index in 0..count {
        let (x, y, z) = position(input, index);
        if x.abs() > COORDINATE_BOUND || y.abs() > COORDINATE_BOUND || z.abs() > COORDINATE_BOUND {
            return Err(KernelFault {
                exit_code: FAULT_COORDINATE_BOUND,
                detail: "a coordinate exceeds |c| <= 2^20",
            });
        }
    }

    let mut energy: i128 = 0;
    for i in 0..count {
        for j in (i + 1)..count {
            let (xi, yi, zi) = position(input, i);
            let (xj, yj, zj) = position(input, j);
            let dx = (xi as i128) - (xj as i128);
            let dy = (yi as i128) - (yj as i128);
            let dz = (zi as i128) - (zj as i128);
            let r2 = dx * dx + dy * dy + dz * dz;
            if r2 == 0 {
                return Err(KernelFault {
                    exit_code: FAULT_COINCIDENT,
                    detail: "two particles are coincident",
                });
            }
            energy += REPULSIVE_NUMERATOR / (r2 * r2) - ATTRACTIVE_NUMERATOR / r2;
        }
    }
    Ok(energy.to_le_bytes())
}
