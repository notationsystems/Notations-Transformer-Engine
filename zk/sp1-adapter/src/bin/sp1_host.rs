//! sp1-host: the cross-process driver for proving and verifying.
//!
//! Mirrors `execution-cli`'s discipline: line-oriented, deterministic
//! output; every identity echoed here is recomputable by the caller, and
//! the Python layer recomputes and compares them all.
//!
//! ```text
//! sp1-host prove  <elf> <program-id-hex> <input-hex> <proof-out>
//! sp1-host verify <elf> <program-id-hex> <proof-in>
//!                 <expect-program-hex> <expect-input-hex>
//!                 <expect-output-hex> <expect-exit>
//! ```
//!
//! `verify` builds the full four-part `Expectation` and runs it through
//! the sealed `ProofBackend::verify` entry point -- the same path any
//! in-process caller uses, embedded statement, coverage clamp and all.
//! Its report names the outcome exactly; a `failed` or `unsupported`
//! outcome exits 0 (the QUESTION was answered), while a protocol or
//! environment error exits nonzero (no answer exists).

use std::io::Write;

use execution_core::{
    Expectation, ProofArtifact, ProofBackend, VerificationResult, VerifiedExecution,
};
use sp1_adapter::Sp1PairwiseBackend;

fn from_hex(text: &str) -> Result<Vec<u8>, String> {
    if !text.len().is_multiple_of(2) {
        return Err(format!("odd-length hex: {text:?}"));
    }
    (0..text.len())
        .step_by(2)
        .map(|at| u8::from_str_radix(&text[at..at + 2], 16).map_err(|e| e.to_string()))
        .collect()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match run(&args) {
        Ok(()) => {}
        Err(error) => {
            eprintln!("sp1-host error: {error}");
            std::process::exit(2);
        }
    }
}

fn run(args: &[String]) -> Result<(), String> {
    let command = args.get(1).map(String::as_str).ok_or("missing command")?;
    match command {
        "prove" => prove(args),
        "verify" => verify(args),
        other => Err(format!("unknown command {other:?}")),
    }
}

fn setup(elf_path: &str, program_id_hex: &str) -> Result<Sp1PairwiseBackend, String> {
    let elf = std::fs::read(elf_path).map_err(|e| format!("reading {elf_path}: {e}"))?;
    // The descriptor identity the guest is registered as implementing is
    // supplied by the caller as its 64-hex digest; reconstruct the typed
    // identity by round-tripping through the expectation constructor is
    // not possible from a digest alone, so the caller passes the
    // DESCRIPTOR BYTES via file for binding registration.
    let descriptor = std::fs::read(program_id_hex)
        .map_err(|e| format!("reading descriptor file {program_id_hex}: {e}"))?;
    let binding = execution_core::ProgramIdentity::of(&descriptor);
    Sp1PairwiseBackend::setup(elf, binding).map_err(|e| format!("setup: {e:?}"))
}

fn prove(args: &[String]) -> Result<(), String> {
    let [_, _, elf_path, descriptor_path, input_hex, proof_out] = args else {
        return Err("usage: prove <elf> <descriptor-file> <input-hex> <proof-out>".into());
    };
    let backend = setup(elf_path, descriptor_path)?;
    let input = from_hex(input_hex)?;

    let (proof_bytes, statement) = backend.prove(&input).map_err(|e| format!("prove: {e:?}"))?;
    std::fs::write(proof_out, &proof_bytes).map_err(|e| format!("writing proof: {e}"))?;

    let mut out = String::new();
    out.push_str("sp1-host-result v1\n");
    out.push_str("command prove\n");
    out.push_str(&format!(
        "backend {} {}\n",
        backend.backend().name,
        backend.backend().version
    ));
    out.push_str(&format!("vkey_hash {}\n", backend.vkey_hash()));
    out.push_str(&format!(
        "input_commitment {}\n",
        statement.input_commitment_hex
    ));
    match &statement.output_commitment_hex {
        Some(output) => {
            out.push_str("guest_status completed\n");
            out.push_str(&format!("output_commitment {output}\n"));
        }
        None => out.push_str("guest_status halted\n"),
    }
    out.push_str(&format!("exit_code {}\n", statement.exit_code));
    out.push_str(&format!("proof_bytes {}\n", proof_bytes.len()));
    print!("{out}");
    std::io::stdout().flush().map_err(|e| e.to_string())
}

fn verify(args: &[String]) -> Result<(), String> {
    let [_, _, elf_path, descriptor_path, proof_in, expect_program, expect_input, expect_output, expect_exit] =
        args
    else {
        return Err(
            "usage: verify <elf> <descriptor-file> <proof-in> <expect-program-hex> \
             <expect-input-hex> <expect-output-hex> <expect-exit>"
                .into(),
        );
    };
    let backend = setup(elf_path, descriptor_path)?;
    let proof_bytes = std::fs::read(proof_in).map_err(|e| format!("reading proof: {e}"))?;
    let artifact = ProofArtifact::new(backend.backend().clone(), proof_bytes);

    // Typed identities are built from PREIMAGES, never accepted as bare
    // digests -- so the caller supplies preimages: the program as a file
    // ("registered" = the descriptor this backend is bound to; any other
    // value = a path to an alternate program's bytes, which is how the
    // altered-program tamper test asks its question), input and output
    // as hex bytes.
    let program = execution_core::ProgramIdentity::of(
        &std::fs::read(if expect_program == "registered" {
            descriptor_path.clone()
        } else {
            expect_program.clone()
        })
        .map_err(|e| format!("reading program preimage: {e}"))?,
    );
    let input_bytes = from_hex(expect_input)?;
    let output_bytes = from_hex(expect_output)?;
    let exit: u32 = expect_exit.parse().map_err(|e| format!("exit code: {e}"))?;

    let expectation = Expectation::of_program(program)
        .with_input(execution_core::InputIdentity::of(&input_bytes))
        .with_output(execution_core::OutputIdentity::of(&output_bytes))
        .with_exit_code(exit);

    let result = backend.verify(&artifact, &expectation);

    let mut out = String::new();
    out.push_str("sp1-host-result v1\n");
    out.push_str("command verify\n");
    match &result {
        VerificationResult::Verified {
            coverage,
            proof,
            backend: by,
            ..
        } => {
            let verified = VerifiedExecution::from_result(&result)
                .expect("Verified results always yield a VerifiedExecution");
            out.push_str("outcome verified\n");
            out.push_str(&format!(
                "coverage program={} input={} output={} exit_code={}\n",
                coverage.program_checked,
                coverage.input_checked,
                coverage.output_checked,
                coverage.exit_code_checked
            ));
            out.push_str(&format!("proof_identity {}\n", proof.to_hex()));
            out.push_str(&format!("backend {} {}\n", by.name, by.version));
            out.push_str(&format!(
                "statement_program {}\n",
                verified.expectation().program().to_hex()
            ));
        }
        VerificationResult::Failed {
            failure, coverage, ..
        } => {
            out.push_str("outcome failed\n");
            out.push_str(&format!("failure {failure:?}\n"));
            out.push_str(&format!(
                "coverage program={} input={} output={} exit_code={}\n",
                coverage.program_checked,
                coverage.input_checked,
                coverage.output_checked,
                coverage.exit_code_checked
            ));
        }
        VerificationResult::Unsupported { missing, .. } => {
            out.push_str("outcome unsupported\n");
            out.push_str(&format!("missing {missing:?}\n"));
        }
    }

    print!("{out}");
    std::io::stdout().flush().map_err(|e| e.to_string())
}
