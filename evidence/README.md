# Public evidence scope

The [project explanation](../README.md#what-this-project-achieves) distinguishes the achievements represented here: one-hour selected sample streaming, separate controlled-source detection and historical finite real Wi-Fi reception. The BCM43455 diagnostic collector already existed; sustained checked export is the specific implementation contribution. Related ESP-SDR streaming is already documented. Neither these aggregates nor sample access establish a first-ever discovery or a practical calibrated general-purpose receiver.

[Run inputs](runs.json), [run table](runs.csv), [audit summary](audit-summary.json) and [claim table](claims.csv) are aggregate derivatives of retained saved-audit records. Source audit hashes identify the exact reviewed result files. They do not by themselves prove public availability or experimental truth.

Retained research history includes firmware watchdog traps, host queue exhaustion, networking control stalls and timing refusals. Those outcomes remain part of the research record. The report presents accepted operating points and general limitations without narrating individual unsuccessful trials.

[Sixstream delivery bins](derived/sixstream-c-delivery.json) contain counts from actual userspace receipt timestamps with absolute host times removed. They support the delivery chart and its arithmetic. Original packet/sample payloads are excluded.

[Finite RF results](rf-findings.json) curate the later channel-1 sparse comparison, including its failed wanted-band gate. They are distinct from sustained-stream tests and do not expand the short sparse run's duration claim.

Prior complete audits checked full recordings, publisher checksums, sequences, wire/control evidence, normal stop and retained health. This preparation curates those records, inspects implementation and performs the explicitly reported local checks. It does not claim a new laboratory experiment or independent hardware replication.

[Preparation checks](preparation-checks.json) record the fresh complete data-frame verification of Private long B, Sixstream C and Sparse A by the new offline parser. These checks are narrower than the full historical wire/health audits. The original files remain private.

The [data availability statement](data-availability.md) specifies what public readers can reproduce. [Reproduction instructions](../docs/reproducing.md) separate synthetic testing, aggregate arithmetic and supplied-recording verification.

The 0.2.0-dev [follow-up registry](followup-findings.json) selects later sparse32/twin6 duration and finite selected-line results. It also includes the failed primary correlation result from the source-marked continuous trial. These are aggregate derivatives of completed separate audits, not new publication-preparation hardware experiments. The private original recordings and all prior snapshots remain unchanged.

The 0.3.0 selection includes the separate STEP0 known-source demonstration:244,160 frames/250,019,840 words/300.025188989 host seconds, two bounded source bursts and 80/80 preset RF chunks. Forty optional neighbor medians remain unavailable (null); conditional floors are descriptive. Exact native and full module rebuilds pass. The private controller is withheld and the hardware experiment is not turnkey. See [known-signal findings](known-signal-findings.json) and [source build](../src/device/BUILD.md).

The [long-run selection](longrun-findings.json) records separate passive ten-minute and one-hour twin6 trials and observed raw-position rollovers. It also records twelve independently replayed historical full-rate Wi-Fi frames with checksum/residue and corruption controls. The passive hour has no current continuous protocol-decoding result; the five-minute STEP0 burst measurements remain separate and unchanged. Original waveforms, identifiers and the acquisition controller are excluded.


The earlier ABI36 hour attempt failed after 2,618,002 delivered frames and 2,680,834,048 words over 3217.027612620 host seconds. Its delivered prefix passes the full saved checks, but normal STOP and the stopped-tail acceptance failed. Stock recovery passed separately. The first TSF low-word rollover is a qualified cause because the rejected snapshot was not retained. The new ABI37 revision uses a bounded coherent clock read and retains a first rejection witness; a successful later recording does not prove that the retry branch executed.

The historical source recipe at src/device reproduces the tested ABI36 b4b image and complete d437 module. The separate ABI37 recipe at src/device-abi37 reproduces the complete 652,800-byte 58a image and 656,600-byte 44c driver module with the documented pinned inputs and toolchains. The fresh unprivileged standalone build matches the full module SHA and all 45 allocated/relocation sections; it installs nothing. Native ELF debug and symbol bytes can differ with paths even when the composed image is exact. These are software-build results; the acquisition and recovery controller remains private.
