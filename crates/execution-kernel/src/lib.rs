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

extern crate alloc;

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

// ---------------------------------------------------------------------
// Second kernel (STE stage 4): 1-D heat diffusion -- an explicit
// finite-difference PDE integrator, a fundamentally different
// computational structure from the pairwise kernel: time-stepped
// nearest-neighbour stencil vs all-pairs accumulation.
// ---------------------------------------------------------------------

/// Heat-kernel fault: input shape is wrong (too short, or not 8 + 8n bytes).
pub const HEAT_FAULT_MALFORMED: u32 = 2;
/// Heat-kernel fault: fewer than 3 nodes (no interior to diffuse).
pub const HEAT_FAULT_TOO_SMALL: u32 = 3;
/// Heat-kernel fault: node count exceeds 4096 or steps exceed 100000.
pub const HEAT_FAULT_BOUNDS: u32 = 4;
/// Heat-kernel fault: an initial value exceeds |u| <= 2^40.
pub const HEAT_FAULT_VALUE_BOUND: u32 = 5;

const HEAT_MAX_NODES: usize = 4096;
const HEAT_MAX_STEPS: u32 = 100_000;
const HEAT_VALUE_BOUND: i64 = 1 << 40;

/// Explicit finite-difference integration of the 1-D heat equation on a
/// fixed grid, entirely in integer arithmetic.
///
/// ```text
/// input  := [steps: u32 LE][n: u32 LE][n x i64 LE initial values]
/// bounds := 3 <= n <= 4096; steps <= 100000; |u_i| <= 2^40
/// step   := for i in 1..n-1 (Dirichlet: u_0 and u_{n-1} fixed):
///             u'_i = u_i + (u_{i-1} - 2*u_i + u_{i+1}) / 4
///           integer division truncating toward zero (alpha = 1/4 is
///           inside the explicit-scheme stability bound of 1/2)
/// output := n x i64 LE final values
/// exit   := 0
/// ```
///
/// The update is computed against the PREVIOUS step's values (a carried
/// `left_old`), never against half-updated ones -- the scheme is Jacobi,
/// not Gauss-Seidel, and which one runs is part of the semantics the
/// descriptor commits to.
pub fn heat_diffusion(input: &[u8]) -> Result<alloc::vec::Vec<u8>, KernelFault> {
    if input.len() < 8 {
        return Err(KernelFault {
            exit_code: HEAT_FAULT_MALFORMED,
            detail: "input shorter than the 8-byte header",
        });
    }
    let steps = u32::from_le_bytes([input[0], input[1], input[2], input[3]]);
    let count = u32::from_le_bytes([input[4], input[5], input[6], input[7]]) as usize;
    if input.len() != 8 + 8 * count {
        return Err(KernelFault {
            exit_code: HEAT_FAULT_MALFORMED,
            detail: "input length is not 8 + 8*n bytes",
        });
    }
    if count < 3 {
        return Err(KernelFault {
            exit_code: HEAT_FAULT_TOO_SMALL,
            detail: "fewer than 3 nodes: no interior to diffuse",
        });
    }
    if count > HEAT_MAX_NODES || steps > HEAT_MAX_STEPS {
        return Err(KernelFault {
            exit_code: HEAT_FAULT_BOUNDS,
            detail: "node count or step count exceeds the descriptor's bounds",
        });
    }

    let mut values = alloc::vec::Vec::with_capacity(count);
    for index in 0..count {
        let at = 8 + index * 8;
        let value = i64::from_le_bytes([
            input[at],
            input[at + 1],
            input[at + 2],
            input[at + 3],
            input[at + 4],
            input[at + 5],
            input[at + 6],
            input[at + 7],
        ]);
        if value.abs() > HEAT_VALUE_BOUND {
            return Err(KernelFault {
                exit_code: HEAT_FAULT_VALUE_BOUND,
                detail: "an initial value exceeds |u| <= 2^40",
            });
        }
        values.push(value);
    }

    for _ in 0..steps {
        let mut left_old = values[0];
        for i in 1..count - 1 {
            let old = values[i];
            values[i] = old + (left_old - 2 * old + values[i + 1]) / 4;
            left_old = old;
        }
    }

    let mut output = alloc::vec::Vec::with_capacity(count * 8);
    for value in &values {
        output.extend_from_slice(&value.to_le_bytes());
    }
    Ok(output)
}
