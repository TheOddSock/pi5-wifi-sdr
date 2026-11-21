# Version 0.4.0

**Raspberry Pi 5 onboard Wi-Fi captures 80 MSPS I/Q snapshots, streams continuously on 2.4 and 5.2 GHz, and decodes an over-the-air Bluetooth LE packet.**

Version 0.4.0 (21 November 2026) preserves all v0.3.0 evidence, source recipes, and the archived October 6 technical report (`pi5-receive-stream.pdf`), and adds eight live over-the-air RF characterizations ([technical addendum](../docs/rf-characterization-20261121.md), [companion addendum PDF](../pi5-rf-characterization-v0.4.0.pdf), [interactive showcase](../site/dist/rf-characterization.html), and [aggregate JSON](../evidence/rf-characterization-20261121.json)):

- **80.000 MSPS wideband snapshots (stock `brcmfmac.ko`):** Scaling `pre/post` within the firmware `0x4000` (`16,384`-word) buffer gate (`100/100 µs` @ 80 MSPS) verified live reception at `+15 MHz` (`+56.0 dB` SNR) and `+30 MHz` (`+50.4 dB` SNR) on `5.210 GHz` with an exact `3,072`-bin step; `country=US` unlocked 5.8 GHz (`Ch 149–165`, `Ch 155 80 MHz`), reaching `+59.33 dB` at `5825.5 MHz` and `+51.96 dB` at `5805 MHz`.
- **Dual-band continuous raw I/Q streaming:** Verified live on 2.4 GHz (`833.33 kSPS`, `+55.8 dB` SNR, conjugated I/Q orientation, `18.99 dB` measured 1st-alias rejection across an audited 3-visit pilot) and 5.2 GHz (`769.23 kSPS` `13/8` profile, `8,192` frames across `10.904 s`, 0 drops, **`+63.00 dB`** peak SNR, `0.072 ppm` drift).
- **Live over-the-air Bluetooth LE decode (zero generator):** Pure-software GFSK demodulation of ambient `20 MSPS` raw I/Q on BLE Advertising Ch 38 (`2426 MHz`) recovered a live `SCAN_RSP` (`0x8E89BED6` `32/32`, `len=16`, `CRC-24 PASS`, identifying device address/payload redacted).
- **TIA capacitor sweep:** Doubling `CFG2.C2` (`20→40`) changed full-rate tone amplitude by `-0.61`, `-0.27`, and `+0.22 dB` at `+40 kHz`, `+833 kHz`, and `+5.040 MHz`, while verifying exact `20.000 MSPS` burst capture.

Stock Raspberry Pi 5 `brcmfmac.ko` (`01-b677b91b`) and Wi-Fi operation were verified after recovery for every experiment. See [limitations](../docs/limitations.md) for retained caveats.

---

## Version 0.3.0

Experimental radio-sample streaming from the Raspberry Pi 5's BCM43455c0 Wi-Fi chip, inspired by ESP-SDR. An existing finite diagnostic collector is adapted for sustained, checked export through reusable buffers into Linux.

The accepted ABI37 twin6 recording delivers 3,000,238,080 complex words over 3600.316538804 host seconds. A separate ten-minute recording passes. A separate five-minute STEP0 experiment detects two bounded source bursts, with 80/80 predeclared RF chunks passing. Twelve historical full-rate finite Wi-Fi frames are independently replayed with valid checksums; this is not continuous decoding on the reduced-rate stream.

Included: illustrated overview, PDF report and appendix, original diagrams, aggregate evidence, synthetic fixtures, offline tools, and exact ABI36/ABI37 source-build recipes. Evidence selection is through 6 October 2026. Original outcomes are retained in the [evidence registries](../evidence/README.md).

The ABI37 recipe reproduces the complete 652,800-byte native image and 656,600-byte driver module using documented inputs and toolchains. Manufacturer binaries, full ambient recordings and the operational acquisition/recovery controller are excluded. Hardware acquisition is not turnkey.

Comprehensive anti-alias filtering, calibrated RF bandwidth/clocks, complete-input physical continuity, continuous packet decoding and reliability beyond tested workloads remain unestablished. See [limitations](../docs/limitations.md).

Original code uses GPL-2.0-or-later; original report, diagrams and documentation use CC BY 4.0. Existing upstream terms remain applicable. [Licence scopes](../LICENSE.md), [AI assistance](../AI_ASSISTANCE.md), and [source availability](../src/README.md) accompany this version.
