# Current findings

Version 0.3.0 includes evidence selected through 6 October 2026. Start with the [illustrated overview](../site/dist/index.html) or [project explanation](../README.md#what-this-project-achieves).

Inspired by ESP-SDR, the project adapts an existing finite BCM43455c0 diagnostic collector into sustained, checked export to Linux. It demonstrates experimental sample access using the Pi 5's existing Wi-Fi chip. Related sample access and continuous streaming predate this implementation; see the [comparison](../evidence/prior-art-comparison.csv).

## Accepted duration and reception results

The accepted passive ABI37 twin6 recording delivers 2,929,920 frames containing 3,000,238,080 complex words over 3600.316538804 host seconds. Sequence/checksum verification, normal STOP, paired restoration, 128 newest-tail references and retained-health checks pass. Raw-position metadata crosses the 32-bit boundary 11 times under the reviewed bounded-progress contract. A separate ten-minute recording passes with 500,039,680 words over 600.051726406 seconds. [Duration aggregates](../evidence/longrun-findings.json).

The separate STEP0 five-minute demonstration delivers 244,160 frames and 250,019,840 complex words over 300.025188989 host seconds. Two bounded source bursts produce 80/80 passing predeclared RF chunks. The minimum amplitude ratio is 26.733 against adjacent OFF95, exceeding the fixed tenfold criterion. Forty optional neighbor medians are unavailable; conditional floors are descriptive. [Known-signal findings](../evidence/known-signal-findings.json).

Independent offline replay recovers twelve checksum-valid Wi-Fi frames from historical full-rate finite records, including checksum/residue checks and corruption controls. This is separate from the reduced-rate continuous stream. No continuous packet decoder is demonstrated.

## Processing and source availability

Twin6 combines six selected inputs with ideal weights [1,2,1,1,2,1]/8 at offsets 0,1,2,8,9,10, then advances sixteen input positions. Exact signed arithmetic is specified in the appendix. Its partial filtering does not establish a calibrated alias-free passband. Earlier sparse-four and six-input configurations retain their own measured scopes in the [follow-up registry](../evidence/followup-findings.json) and [finite RF findings](../evidence/rf-findings.json).

The ABI37 source recipe reproduces the complete 652,800-byte 58a firmware image and 656,600-byte 44c driver module in the documented environment. All 96 reconstructed driver source hashes and 45 allocated/relocation sections match. The separate ABI36 recipe is retained. These are build results, not new hardware trials; the operational acquisition/recovery controller remains private. See [source availability](../src/README.md).

Capture mode 17 is associated with the vendor-labelled `rx_filt_1core` receive path. Exact ordering relative to all internal receive filters and corrections remains uncharacterised. Comprehensive anti-alias filtering, RF/clock calibration, continuous decoding and reliability beyond tested workloads remain open. See [limitations](limitations.md). The [evidence overview](../evidence/README.md) retains historical outcomes; future findings require a new [versioned selection](updating.md).
