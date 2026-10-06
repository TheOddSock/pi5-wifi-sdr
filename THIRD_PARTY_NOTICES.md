# Upstream work and third party notices

This research depends on knowledge and tools from several projects. Citing them does not establish that all their components share a licence or that their authors endorse this implementation.

- Matthias Schulz, Daniel Wegemer and Matthias Hollick, Nexmon: The C-based Firmware Patching Framework, 2017. [Project](https://nexmon.org), [repository](https://github.com/seemoo-lab/nexmon).
- Francesco Gringoli, Matthias Schulz, Jakob Link and Matthias Hollick, Free Your CSI: A Channel State Information Extraction Platform For Modern Wi-Fi Chipsets, WiNTECH 2019. [Paper](https://doi.org/10.1145/3349623.3355477), [Nexmon CSI](https://github.com/seemoo-lab/nexmon_csi).
- SEEMOO, Nexmon software-defined radio project associated with MobiSys 2018. [Repository](https://github.com/seemoo-lab/mobisys2018_nexmon_software_defined_radio).
- ESPARGOS and contributors, ESP-SDR. [Repository](https://github.com/ESPARGOS/esp-sdr). This project was inspired by ESP-SDR, which exposes receive waveforms to software and includes continuous streaming on Espressif chips. Our BCM43455c0 implementation adapts an existing diagnostic collector for sustained checked export; continuous Wi-Fi-chip SDR and generic buffer/integrity techniques are established ideas. [Pinned comparison](evidence/prior-art-comparison.csv).
- Linux and Raspberry Pi kernel contributors, the brcmfmac host driver and tested kernel environment.

The source-only package includes small Linux patch contexts and the exact ISC notices plus upstream whole-kernel GPL-2.0/COPYING texts. The full kernel, manufacturer image, ROM and compiled products are excluded. The original component inventory and pinned origins are retained in src/device/RIGHTS.md and dependencies.json. The outer [licence grant](LICENSING.md) and [exact map](release/component-licences.csv) apply GPL-2.0-or-later to original contributions while preserving upstream terms and the tested source-code bytes.

The Nexmon CSI README includes publication citation requirements. The bibliography includes its specified framework and CSI references; actual component licences still require inspection.

- Pair-Fi and its authors: finite raw BCM4389c1 capture is included in the pinned comparison. [Primary source](https://github.com/seemoo-lab/Pair-Fi).
- Shadow Wi-Fi, MobiSys2018: related raw transmission/channel-estimate research. [DOI](https://doi.org/10.1145/3210240.3210333).
