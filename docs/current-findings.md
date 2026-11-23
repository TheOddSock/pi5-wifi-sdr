# Current findings

Version 0.4.0 preserves all v0.3.0 evidence through 6 October 2026 and adds eight live over-the-air RF characterizations from 21 November 2026. Start with the [illustrated overview](../site/dist/index.html), the [v0.4.0 interactive RF showcase](../site/dist/rf-characterization.html), or [project explanation](../README.md#what-this-project-achieves).

## Live RF characterization addendum (v0.4.0, 2026-11-21)

Eight live over-the-air experiments on the Raspberry Pi 5 `BCM43455c0` ([full summary](rf-characterization-20261121.md), [aggregates](../evidence/rf-characterization-20261121.json)) establish:

- **Physical I/Q orientation & 2.4 GHz CW tracking:** Stepping a MAX2871 CW tone by `+100 kHz` shifted the baseband tone by `-100.391 kHz` (`+55.8 dB` SNR), proving conjugated I/Q (`f_RF > f_LO -> negative baseband`, corrected via `conj(iq)`) and `~8.3 ppm` combined LO offset.
- **Measured `stride16` alias rejection & TIA capacitor sensitivity:** A complete 3-visit audited pilot (`rf06`/`rf07`/`rf08`, `24,416` frames each at `833.33 kSPS`) measured **`18.99 dB`** 1st-alias (`+833 kHz`) rejection. Interleaved full-rate analog TIA capacitor doubling (`CFG2.C2: 20 -> 40 -> 20`) changed tone amplitude by `-0.61`, `-0.27`, and `+0.22 dB` at `+40 kHz`, `+833 kHz`, and `+5.040 MHz` (without isolating exact digital vs analog contributions) while verifying exact `20.000 MSPS` burst capture.
- **Dual-band 5.2 GHz continuous streaming:** Using the Ch 40 (`5200 MHz`, `0xd028`) `13/8` firmware profile (`769.23 kSPS` nominal, `769.225 kSPS` measured), `8,192 / 8,192` continuous frames (`8,388,608` samples across `10.904 s`, 0 drops) received `5200.040 MHz` at `-66.387` to `-66.763 kHz` (`0.072 ppm` drift) with **`+63.00 dB`** peak SNR.
- **`40 / 80.000 MSPS` wideband snapshots & 5.8 GHz unlock (stock `brcmfmac.ko`):** Scaling `pre/post` within the firmware `0x4000` (`16,384`-word) gate (`100/100 µs` @ 80 MSPS = `16,000` words) unlocked `80 MSPS` snapshots at `5210 MHz` (`+56.0 dB` at `+15 MHz`, `+50.4 dB` at `+30 MHz`, exact `3,072`-bin step; a calibrated 80 MHz flat passband is not claimed). Switching `country` from `GB` to `US` unlocked `5.8 GHz` (`Ch 149–165` & `80 MHz Ch 155`), reaching `+59.33 dB` SNR at `5825.5 MHz` and `+51.96 dB` at `5805 MHz`.
- **Live over-the-air Bluetooth LE decode (no generator):** Pure-software GFSK demodulation of ambient `20 MSPS` raw I/Q on Ch 4 (`2427 MHz`) recovered a live BLE Advertising Ch 38 (`2426 MHz`) `SCAN_RSP` packet (`len=16`, `0x8E89BED6` `32/32` bits, CFO `+14.7 kHz`, device address & identifying payload bytes redacted in current release files) with **CRC-24 verified in software (`CRC-24 PASS`)**.

Inspired by ESP-SDR, the project adapts an existing finite BCM43455c0 diagnostic collector into sustained, checked export to Linux. It demonstrates experimental sample access using the Pi 5's existing Wi-Fi chip. Related sample access and continuous streaming predate this implementation; see the [comparison](../evidence/prior-art-comparison.csv).

## Accepted duration and reception results

The accepted passive ABI37 twin6 recording delivers 2,929,920 frames containing 3,000,238,080 complex words over 3600.316538804 host seconds. Sequence/checksum verification, normal STOP, paired restoration, 128 newest-tail references and retained-health checks pass. Raw-position metadata crosses the 32-bit boundary 11 times under the reviewed bounded-progress contract. A separate ten-minute recording passes with 500,039,680 words over 600.051726406 seconds. [Duration aggregates](../evidence/longrun-findings.json).

The separate STEP0 five-minute demonstration delivers 244,160 frames and 250,019,840 complex words over 300.025188989 host seconds. Two bounded source bursts produce 80/80 passing predeclared RF chunks. The minimum amplitude ratio is 26.733 against adjacent OFF95, exceeding the fixed tenfold criterion. Forty optional neighbor medians are unavailable; conditional floors are descriptive. [Known-signal findings](../evidence/known-signal-findings.json).

Independent offline replay recovers twelve checksum-valid Wi-Fi frames from historical full-rate finite records, including checksum/residue checks and corruption controls. This is separate from the reduced-rate continuous stream. No continuous packet decoder is demonstrated.

## Processing and source availability

Twin6 combines six selected inputs with ideal weights [1,2,1,1,2,1]/8 at offsets 0,1,2,8,9,10, then advances sixteen input positions. Exact signed arithmetic is specified in the appendix. Its partial filtering does not establish a calibrated alias-free passband. Earlier sparse-four and six-input configurations retain their own measured scopes in the [follow-up registry](../evidence/followup-findings.json) and [finite RF findings](../evidence/rf-findings.json).

The ABI37 source recipe reproduces the complete 652,800-byte 58a firmware image and 656,600-byte 44c driver module in the documented environment. All 96 reconstructed driver source hashes and 45 allocated/relocation sections match. The separate ABI36 recipe is retained. These are build results, not new hardware trials; the operational acquisition/recovery controller remains private. See [source availability](../src/README.md).

Capture mode 17 is associated with the vendor-labelled `rx_filt_1core` receive path. Exact ordering relative to all internal receive filters and corrections remains uncharacterised. Comprehensive anti-alias filtering, RF/clock calibration, continuous decoding and reliability beyond tested workloads remain open. See [limitations](limitations.md). The [evidence overview](../evidence/README.md) retains historical outcomes; future findings require a new [versioned selection](updating.md).
