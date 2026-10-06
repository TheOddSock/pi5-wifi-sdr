# Implementation appendix
This appendix describes the inspected V26 selected-stream implementation and its six-input append. The short sparse follow-up shares the publication ABI but has different input offsets and a channel-specific timing pair. The descriptions below are source-equivalent explanations; the included source-only recipe exactly rebuilds the later twin6 image/module; manufacturer input terms and the withheld operational controller still limit complete public hardware reproduction.

## A Compatibility and ownership

The implementation is bound to BCM43455c0 manufacturing firmware 7.120.5.1 C0 WLTEST, the patched V26 image layout and a specific Linux brcmfmac module. The module checks the chip/revision, SDIO state/clock, code fingerprint, owned-RAM descriptor and single-session quotas. A matching chip family name alone does not admit another image.

The preserved upstream MFG base image is 507,048 bytes, SHA-256 a8793f02aed5730fc8020e93e49911e6183458497e0b26be633a2e35d337ab8a, identified in the project at Nexmon revision 68720406f54ff16cad28fd3c51f2392aefad9fb7. The identified path is firmwares/bcm43455/7_120_5_1_sta_C0/bcmdhd_mfg.bin_blob. This is an acquisition lead, not a verified redistribution permission. [Identified upstream location](https://github.com/seemoo-lab/nexmon/blob/68720406f54ff16cad28fd3c51f2392aefad9fb7/firmwares/bcm43455/7_120_5_1_sta_C0/bcmdhd_mfg.bin_blob)

The experimental sample workspace is outside vendor heap ownership after the reviewed heap/CRC adjustment. The original first-32-byte text fingerprint and fixed record addresses are preserved by the six-input append. Its assembly accesses the record at 0x216980. These addresses are image-specific and are not general chip register specifications. Cache admission requires observed SCTLR data-cache bit 2 clear; the implementation does not silently reconfigure caching to satisfy that condition.

The owned record occupies 33,664 bytes: a 128-byte descriptor, eight 4,128-byte slots and a 512-byte stopped reference. Other progress, context, phase, lease and watchdog workspace is additional. A complete build must retain native ROM helper resolution, hook redirects, linker ownership, image CRC/heap changes and the matching driver contract.

### A1 Baseline identities and collector addresses

The source collector extent is 0x8000 through 0xBFFF in word-address units, comprising 16,384 words or 65,536 bytes. The firmware converts a word position into the selector byte address by shifting left two bits. It accesses selector/data ports at offsets 0x130 and 0x134 from the verified context. The sample collector's physical tap and undocumented clock circuitry remain qualified.

The unfiltered V26 image SHA-256 is 69cef337c50de6a2ccef6a7402c919c74b3fed973b14bf19996a8f52fc515b4e. The six-input image SHA-256 is 07ab31ff7cd78a682f493ece9e3923d58a1d1a9dbf288d31c48cc89eface2dac. Their shared private-stream module SHA-256 is be069e1217374b74679f1a53515c7d7f634c324a46a54c8606b85cb12ece1301. The registry also identifies the different lease and sparse configurations. Firmware and host-driver compatibility are part of the mechanism, not interchangeable environmental details.

## B Collector request and lifecycle

The fixed request uses the 48-byte version 2 sample_collect ABI with trigger 1, timeout 2, mode 17, nominal pre/post 400/400 and otherwise zero reserved fields. These finite request fields do not describe the long capture duration. The patched collector polling/stop/lease lifecycle determines the sustained experiment's end.

| Stage | Behaviour and evidence requirement |
|---|---|
| Admission | Exact arguments, context, fingerprint, idle session, initial heartbeat and nonzero native watchdog predicates pass |
| Preparation | Initialise owned descriptor and state; save native controls/selectors; apply and verify the chosen full timing pair where relevant |
| Active collection | Observe writer progress; consume completed inputs; commit output blocks; check stop/lease and service native watchdog |
| Stop or expiry | End collection through the reviewed native path at block alignment; separately account for any unread suffix |
| Stopped reference | Read latest128 with the same selected/filter kernel; compare against the latest retained firmware slot |
| Restoration | Preserve native result, restore/read back full changed pair and selectors, export final telemetry |
| Refusal or fault | Preserve evidence; use the separately bounded recovery contract rather than assuming successful normal restoration |

The six-input wrapper performs native deadman/heartbeat admission before pair mutation. It admits the channel 40 ordinary full pair 0x19ce38e3, writes the requested 0x1ab55554 through the native low-then-high helpers, checks readback and pre-arm state, calls the original target, checks the pair after its stopped reference, then restores the baseline. Error results are preserved. The sparse channel 1 pair is different and must not be inferred from channel 40 literals.

## C Source ring accounting

The hardware word extent is 0x8000..0xBFFF. Its relative writer progression is modulo 2^14. Successive snapshots derive `dw=(pointer-current_previous)&0x3fff` and a modular cycle-counter delta. The inspected source rejects zero or excessive cycle delta above 32768 and observed word advance above 4096. It also requires compatible stopped/active extent, pointer-high, control, clock and context state.

`produced` extends the observed writer progression modulo 2^32. The next input coordinate starts at 64 and follows `next_raw = 64 + 16*output_count`, with modular arithmetic where the reviewed helpers require it. The completion margin is 64 positions. The guarded overwrite limit is 16320, which is 16384 minus 64.

Source-equivalent eligibility is:

```text
d = (produced - next_raw) modulo 2^32
if d has bit31 set, or d <= 64: no completed work
if d >= 16320: refuse excessive lag
available = produced - 64 - next_raw
n = ceil(available / 16)
if n < 32: defer
n = min(n, 128, remaining_positions_in_output_block)
```

The consumer snapshots and checks clock/progress after its reads, rejects `produced-first >= 16320`, checks exact selector restoration and bounds read cost. The active path also preserves the reviewed full-iteration bound of 32768. These conditions depend on their observation/timing assumptions. They do not independently eliminate an unseen complete hardware lap or pause.

The selected-read address is `(0x8000 + (raw & 0x3fff)) << 2`, written to selector offset 0x130, followed by the data read at 0x134. Firmware saves the old selector and restores it through the native template helper. No sample-memory acknowledgement/backpressure is introduced.

## D Signed sample processing

For each packed word, lanes are interpreted as signed 16-bit values. ARM SHADD16 forms the widened signed sum of each lane and arithmetic-shifts it right one bit. The corresponding integer operation is `half(a,b) = floor((a+b)/2)`, including negative odd sums. There is no saturation or narrowing overflow for an average of two signed 16-bit values.

The six-input tree is:

```text
l = half(half(x0, x1), x2)
r = half(x3, half(x4, x5))
y = half(l, r)
```

Its ideal weights are[1,1,2,2,1,1]/8; intermediate rounding makes it different from one final rational weighted sum. The reference utility computes this tree separately per lane. The assembly performs the two lanes simultaneously and advances 16 source positions after each output.

The sparse tree uses inputs at offsets 0, 1, 8 and 9:

```text
y = half(half(x0, x1), half(x8, x9))
```

Its ideal weights are 1/4 at those four positions. Its exact signed result lies within one integer unit below the ideal mean. Both live and stopped-reference paths use the same arithmetic, so their agreement is a consistency check. Separate same-epoch full raw exports establish the arithmetic against independently reconstructed inputs.

The three paths retain a fixed starting input coordinate and stride. Descriptive Hz values follow nominal input/output-rate assumptions; they do not add clock calibration. The kernels are short prefilters rather than established full-band anti-alias low-pass filters.

## E Descriptor and publication slots

The descriptor contains 32 little-endian 32-bit words. Its fields in order are:

```text
magic, version, bytes, capture_sequence, status, flags, count, stride,
first_raw, next_raw, produced, last_pointer, last_cycle, wraps, batches, max_lag,
copy_ticks, max_copy_ticks, restored_count, tail_checked, tail_mismatched,
vendor_result, cleanup, published,
sctlr, steps, total_blocks, block_words, slots, stop_request, stop_observed,
watchdog_feeds
```

The V26 contract uses magic 0x5354524d, version 26, bytes 33664, stride 16, block_words 1024, slots 8 and total_blocks 0xfffffffe as a sentinel bound. Active status is 0 and clean stopped status is 2. Fatal flags/status are refused. Header counters alone do not establish physical-input generation.

| Slot byte offset | Field | Meaning |
|---|---|---|
| 0 | sequence u32 | Zero while reusing; committed generation when valid |
| 4 | first u32 | Output index of the first word |
| 8 | count u32 | 1024 for a complete publication |
| 12 | hash u32 | Word-wise publisher checksum |
| 16 | produced_before u32 | Observed extended raw progression before filling |
| 20 | produced_after u32 | Observed progression after filling |
| 24 | copy_ticks u32 | Summed read work for this block |
| 28 | flags u32 | Zero for accepted data |
| 32 | 1024 u32 words | Little-endian packed signed-lane payload |

Slot selection is `(publication_sequence-1) % 8`. Firmware invalidates sequence, executes DMB SY, writes the payload and metadata, completes the hash, executes DMB SY, writes committed sequence, executes DMB SY and advances `published`. There is no host ACK holding a slot indefinitely. If the host is too slow, refusal protects interpretation rather than recovering discarded generations.

The publisher checksum starts at 2166136261 and folds each packed 32-bit word as `h=((h XOR word)*16777619) modulo 2^32`. This differs from folding four separate bytes. The six-input live assembly seeds at output-block offset 0 and retains the accumulator over partial batches. The original final block rescan is removed, but the checked final commit order is preserved.

## F Host data frame and acceptance

The exported data frame is 4,176 bytes. Scalar fields and payload are little-endian for the tested host. The format is documented independently of C padding below.

| Byte offset | Type | Field |
|---|---|---|
| 0 | u32 | Magic 0x49514652 |
| 4 | u32 | Version 1 |
| 8 | u32 | Frame bytes 4176 |
| 12 | u32 | Kind 1 data frame |
| 16 | u32 | Expected output sequence |
| 20 | u32 | First output index |
| 24 | u32 | Word count 1024 |
| 28 | u32 | Publisher hash |
| 32 | u64 | Kernel acquisition start_ns |
| 40 | u64 | Kernel acquisition end_ns |
| 48 | 8 u32 | Slot metadata copied from firmware |
| 80 | 1024 u32 | Payload |

The kernel first checks the bound code fingerprint and 128-byte descriptor. It requires the expected version/layout, capture identity, stride, sentinel limits, status and flags. A published sequence behind the reader or more than eight blocks ahead is rejected. The kernel reads initial 32-byte slot metadata, a 4096-byte first payload, a 4096-byte second payload and final 32-byte metadata under SDIO host ownership, restoring its backplane window afterward.

Acceptance requires initial/final metadata equality, identical payload copies, expected sequence, exact first index/count, zero flags and checksum equality. Errors propagate to the file reader. The file is nonseekable and tracks partial-read offset within one frame; the acquisition worker assembles a complete frame before queueing it. The offline public verifier sees only the accepted serialized frame, so it cannot repeat the original double-copy predicate without those separate raw copies.

Kind 2 terminal frames and the 1232-byte stop summary have different semantics. The public data-frame parser explicitly refuses them rather than interpreting terminal metadata as sample payload.

## G Watchdog and lease

The native watchdog retains the existing configured deadline of 481500000 and requires a nonzero service interval/handle, exact native handler identity and admitted core context. It invokes the existing refresh routine with argument 1, observes execution cost and verifies deadline/core restoration. No interrupt-mask or watchdog-disable operation is introduced.

The 64-byte lease record includes magic/version/size, host heartbeat, seen token, renewal count, expiry counterticks, last cycle, expired/status, age/max gap, flags and token-wrap telemetry. Initial heartbeat 1 is admitted. Each renewal is the exact next token with UINT32_MAX followed by 1; token 0 is not an accepted wrap. Expiry is half the existing watchdog deadline, 240750000 counterticks, whose conversion to wall-clock time depends on the actual counter.

The host renews after each 128 accepted blocks while capture is active. Firmware separately checks lease age using modular cycle arithmetic. A missing reader can trigger normal expiry and EOF in the preserved expiry experiment. That result is distinct from the 60-second explicit-close run and is not reproduced by a synthetic token test.

## H STOP and control exclusion

The close path checks live image/descriptor/work state, writes the fixed value 0x53544f50 to descriptor byte offset 116 and reads it back. It accepts no caller-selected address or value. The producer observes the owned word, reaches the reviewed stop boundary and returns through the vendor cleanup path.

The stop summary reads the latest published slot's last 128 words and the stopped reference and requires equality with zero descriptor/vendor/tail errors. One extra firmware block can be published after the requested host quota. Therefore the reference may match that unread suffix; comparing it to the last delivered host frame would be the wrong predicate.

The private control path requires CAP_SYS_RAWIO and one matching radio. A module-global admission counter enrolls all participating protocol-mutex callers. A private owner transitions gate 0 to its exclusive sentinel only when no earlier user is enrolled. Other controls return EBUSY; the owner issues one real sample_collect request through the existing BCDC path. The reply is retained rather than fabricated early. This separates long-capture ownership from shared networking control.

## I Host recording and guarded completion

An acquisition thread validates/assembles frames while a bounded writer queue performs buffered file writes. Queue errors, capacity exhaustion, exceptions or unexpected vendor completion cause refusal rather than a successful shortened recording. The original V26 five-minute runs use 8,192 frames; short tests can have smaller bounded queues and must retain their actual identities.

Buffered writes can take longer than on-chip retention, so acquisition and storage are separated. Short write-call timing does not measure durable flush completion. The run's final queue drain and writer termination are checked, with an independent saved-file audit afterward. Error recovery retains the original evidence and verifies restored/retained health under its reviewed procedure. New public deployment wrappers require explicit validation status rather than inheriting historical success automatically.

## J General method and porting constraints

The implemented combination is a circular diagnostic collector, bounded embedded sample consumer, selected/transformed output blocks, ordered reusable-memory publication, concurrent host-interface readout and checked bounded delivery. These abstractions map to the D11 sample ring, Cortex-R4 consumer, slot protocol, SDIO reader and userspace queue described above.

Another target would need demonstrated concurrent sample access, known memory ownership/cache semantics, sufficient service budget, verified host memory reads, control lifetime separation and recovery. Different ring sizes, block lengths, strides, filters, output integrity modes or sinks require explicit arithmetic and bounds. A polyphase or CIC label does not remove required high-rate input reads. No other-board port, sample-memory DMA or arbitrary-bus implementation is established here.

## K Public checks and remaining dependencies

The public verifier checks schema, exact sequence/index, timing ordering, metadata, flags and the word-wise checksum for supplied data frames. Synthetic fixtures test rejection paths. Public aggregate metrics and delivery bins regenerate the available result charts, while original waveform/wire/health evidence remains private.

The included source-only recipe records exact transitive build inputs, toolchains, source hashes and upstream notices and reproduces complete later twin6 firmware/module bytes. Manufacturer inputs must be acquired by the reader under applicable terms. Original project code uses GPL-2.0-or-later; retained upstream terms apply separately. The private operational controller remains withheld, so build reproduction is established while a turnkey hardware experiment is not. This scope limits any claim of complete public experimental reproducibility.

## L Later thirty-two-slot partial-filter configurations

The original appendix sections A-K specify the initial eight-slot V26/six baselines. Later selected sparse32/twin6 trials have ABI35/ABI36 and thirty-two 4,128-byte publication slots. Their 132,736-byte record contains a 128-byte descriptor, 132,096 bytes of slots and a 512-byte stopped reference. Additional workspace and heap/stack admission are still required. Source/module identities are different; none of the earlier addresses constitute a public installation recipe for these versions.

The accepted later reader uses one payload copy surrounded by metadata checks and the publisher checksum. This changes the stability contract from the earlier two-identical-copies path. Guard, sequence, publication, stopped newest-owned-tail and health audits are retained, but copying once is not an independent freshness proof.

The twin6 exact signed kernel at offsets 0,1,2,8,9,10 is:

```text
l = half(half(x0, x2), x1)
r = half(half(x8, x10), x9)
y = half(l, r)
```

Its ideal weights are [1,2,1,1,2,1]/8 at those offsets. Intermediate negative rounding remains part of its actual semantics. Both live and stopped paths use the same kernel; independent finite raw-reference comparisons validate the signed tree separately. The public offline arithmetic utility currently implements the earlier six/sparse kernels; this section specifies the later kernel without implying that the synthetic fixture verifies its device implementation.

## M Exact source-build reproduction and integration boundary

The source-only package includes the transitive native append and minimal kernel reconstruction. A reader supplies the manufacturer image and pinned kernel inputs under their applicable terms. Fresh builds reproduce complete b4b and d437 bytes; the driver comparator also checks 45 allocated/relocation sections, vermagic, srcversion, licence declaration and native fingerprint. No install occurred. Toolchain/header details and receipts are included in the source guide.

The operational controller remains private. A public runner still needs fresh-session admission, exact module/firmware loading, Ethernet management, captured state/rollback, quotas, lease renewal, exclusive control, recording, genuine completion and health checks. The source package is sufficient to reproduce builds; it is not sufficient alone to reproduce the complete hardware experiment. No new untested runner is implied.

## N Duration extension, clock coherence and identities

ABI37's `src/device-abi37` recipe reproduces the exact 652,800-byte 58a image and 656,600-byte 44c module; `src/device` preserves ABI36. Unprivileged builds match the full module SHA and all 45 allocated/relocation sections without installing. Native ELF debug/symbol bytes may vary with paths. Acquisition and recovery controllers remain private.

ABI37 uses bounded coherent clock acquisition across adjacent high-word carries and retains the first rejected-reading diagnostic. The accepted hour includes one observed clock high-word advance; execution of the bounded retry branch is not established by that observation.

The accepted ABI37 hour uses the same signed twin6 leaf and 32-slot layout as the ABI36 ten-minute predecessor. It delivers 2,929,920 frames/3,000,238,080 words over 3600.316538804 host seconds, with 11 observed raw-position uint32 crossings. Its selected-word count exceeds signed32 and remains below unsigned32 rollover; selected-word rollover is untested. Raw positions are wider reconstructions from bounded positive modular metadata and the exported source-ring wrap count/pointer. This does not supply an independent physical-generation counter or exclude hidden whole-ring laps. ABI37 adds one bounded high/low/high clock reread only on an adjacent carry and phase6 first-rejection evidence; other coherence and timing guards still refuse failures. Success rejects every phase6 observation. The matched driver contract changes fingerprints/ABI/addresses while retaining reader ownership, lease renewal, lag, timeout and STOP semantics. The full operational controller remains private.
