# Version 0.3.0

Experimental radio-sample streaming from the Raspberry Pi 5's BCM43455c0 Wi-Fi chip, inspired by ESP-SDR. An existing finite diagnostic collector is adapted for sustained, checked export through reusable buffers into Linux.

The accepted ABI37 twin6 recording delivers 3,000,238,080 complex words over 3600.316538804 host seconds. A separate ten-minute recording passes. A separate five-minute STEP0 experiment detects two bounded source bursts, with 80/80 predeclared RF chunks passing. Twelve historical full-rate finite Wi-Fi frames are independently replayed with valid checksums; this is not continuous decoding on the reduced-rate stream.

Included: illustrated overview, PDF report and appendix, original diagrams, aggregate evidence, synthetic fixtures, offline tools, and exact ABI36/ABI37 source-build recipes. Evidence selection is through 6 October 2026. Original outcomes are retained in the [evidence registries](../evidence/README.md).

The ABI37 recipe reproduces the complete 652,800-byte native image and 656,600-byte driver module using documented inputs and toolchains. Manufacturer binaries, full ambient recordings and the operational acquisition/recovery controller are excluded. Hardware acquisition is not turnkey.

Comprehensive anti-alias filtering, calibrated RF bandwidth/clocks, complete-input physical continuity, continuous packet decoding and reliability beyond tested workloads remain unestablished. See [limitations](../docs/limitations.md).

Original code uses GPL-2.0-or-later; original report, diagrams and documentation use CC BY 4.0. Existing upstream terms remain applicable. [Licence scopes](../LICENSE.md), [AI assistance](../AI_ASSISTANCE.md), and [source availability](../src/README.md) accompany this version.
