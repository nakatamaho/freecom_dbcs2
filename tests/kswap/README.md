# Independent FreeCOM KSSF regression

This work repairs common FreeCOM kernel-swap code, separately from any VA
adapter. The ordinary VA FreeCOM pin and the MS-DOS shell experiment are not
changed by this branch. No VA, hardware or milestone acceptance is implied.

## Changes under test

- Register an actual segment, not the offset obtained by narrowing a Watcom
  FAR pointer.
- Allocate/check the saved environment against its current MCB length at each
  swap. Initial `/E:` resizing therefore cannot overrun an early allocation.
  Allocate a replacement before freeing an old backup; if allocation fails,
  retain the shell and execute without swapping. The failure diagnostic is
  resident: trying to load STRINGS while out of memory could otherwise prompt
  for a resource file instead of reaching the ordinary EXEC fallback.
- Keep the dynamic context allocated across the shell's DOS exit, then return
  its ownership to the reloaded shell. Save the context counters in a reserved
  hex-encoded context entry after its allocation, including the `/LOW` policy.
  Obtain all context pointers after insertions that may relocate the block.
- Free a pending dynamic context on KSSF termination if shell reload failed.
- Collect the child's DOS return code before loading the shell again.

Use COMMAND.COM and KSSF.COM built together. There is no cross-version saved
state compatibility claim. Batch, pipes and redirection of the swapped command
remain unsupported as described in `docs/k-swap.txt`. This work does not turn
KSSF into an XMS or disk swapping implementation.

## Public build and test prerequisites

Use Linux/amd64 Docker, Git, Python 3 and host `unzip`. The compiler is the official final
Open Watcom 1.9; NASM assembles KSSF and the source test programs. The public
identity-locked toolchain setup is reused as an external build dependency:

```sh
git clone https://github.com/nakatamaho/freedos-pc88va.git toolchain-source
git -C toolchain-source checkout 6d4e2dda024d21d3a8380adfa8900201be3bfdcc
python3 -B toolchain-source/tools/m19/toolchain.py
```

That entry point verifies the published tool identities and acquires the
public pinned dependencies. No component binaries or old guest disk from that
project are used. `build.sh` in this directory executes only inside a clean,
network-disabled container source export, not inside the component checkout.
It sets the existing FreeCOM build-date/time definitions from the source Git
commit timestamp; no semantic binary differences are normalized away.

Prepare the independent PC guest runtime (not the compiler container):

```sh
export OUT="$(pwd)/kswap-results"  # outside the FreeCOM checkout; fresh directory
mkdir -p "$OUT"
docker run -d --name kswap-runtime --platform linux/amd64 \
  -v "$OUT:/work" -w /work \
  debian@sha256:f37a335e82bca302e955fa39f9dfe28f1be618f016f8a2b56318e5a5111afc26 \
  sleep infinity
docker exec kswap-runtime sh -ec \
  'apt-get update && apt-get install -y --no-install-recommends qemu-system-x86 mtools'
```

The test records QEMU's version and executable hash; the emulator is a
verification dependency, not a source input to COMMAND.COM. No private ROMs
are used. The source checkout must be clean and committed:

```sh
python3 -B -m unittest discover -s tests/kswap
python3 -B tests/kswap/run.py --output "$OUT" --runtime-container kswap-runtime
```

The runner exports the exact component commit, makes two complete independent
IBM-PC/no-XMS builds, and requires matching COMMAND/KSSF/test program bytes.
It acquires the public FreeDOS 1.4 floppy archive and checks its SHA-256 before
extracting `144m/x86BOOT.img` (kernel 2043). That public, prebuilt PC OS is a
control environment only, never an input to a new VA distribution. The archive
URL and digest are fixed in `run.py`. No saved COMMAND or test executable is an
input. Failed builds and test disks are retained in the excluded output
location. Do not commit them or designate them as a milestone distribution.

## Required checks

- `/E:512` and `/E:8192`: ordinary execution retains COMMAND MCBs; swapped COM
  execution has none and obtains a larger allocation. Twenty consecutive
  swaps must have identical allocation accounting and valid MCB topology.
- Environment, alias, history and command tail survive the swap. A source-built
  relocatable MZ must write its marker and return exactly 7 through the reload.
- `/E:32752`: the source HOG fixture retains memory until reboot, leaving no
  free block larger than 16 KiB. The first backup allocation must fail safely;
  two fresh COM executions must instead retain the shell, finish, and have
  stable allocation accounting. HOG is for disposable guests only.
- Guest-generated output is independently read after QEMU quits. Missing,
  malformed, stale or inconsistent output is failure, not a skipped success.

`probe.asm` and `qmp.py` originated as project-authored M19 public-release
research helpers and are maintained here with the FreeCOM regression. The
probe validates the MCB traversal and writes its own files because redirected
`CALL /S` is not supported. Probe allocation is an EXEC observation, not an
idle-memory or arbitrary-application-capacity claim.

The host suite also executes the legacy CI's NASM ZIP extraction command with
synthetic Unix-origin uppercase entries. `unzip -L` leaves those names uppercase;
`-LL` is required to establish the lowercase directory used by the DOS recipe.
The legacy DOS build preflights `nasm.exe -v` and resolves it through DOS PATH;
this remains a DOS assembler build, not a substitution with the host assembler.

Acceptance is revision-specific: require a successful `result.json` and the
`FreeCOM KSSF regression` CI job on the exact source revision. Borland builds, UMB operation, live environment relocation,
failed shell-reload cleanup and VA/hardware behavior are not qualified by these
cases. Preserve these limits even after the bounded PC regression passes.
