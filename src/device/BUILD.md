# Build and reconstruction instructions

These commands operate on local files. They do not install or activate a receiver.

## Native append and private image composition

Use Python3.11+ with `capstone==5.0.6` and `pyelftools==0.33`, and the tested xPack GNU Arm Embedded GCC9.3.1 20200408 release (PlatformIO package1.90301.200702). The source is freestanding Cortex-R4 Thumb code; no C library or Nexmon framework code is linked. Compiler/libgcc support remains part of the supplied toolchain, not redistributed here.

Supply a legally acquired BCM43455c0 MFG7.120.5.1 image of507048 bytes with SHA256 `a8793f02aed5730fc8020e93e49911e6183458497e0b26be633a2e35d337ab8a`. A historical acquisition lead is [Nexmon commit68720406](https://github.com/seemoo-lab/nexmon/blob/68720406f54ff16cad28fd3c51f2392aefad9fb7/firmwares/bcm43455/7_120_5_1_sta_C0/bcmdhd_mfg.bin_blob); availability there is not redistribution permission. The package does not download it.

```text
python native/build.py --image /path/to/reader-supplied-MFG.bin --toolchain-bin /path/to/arm-none-eabi/bin --out /path/to/fresh-native-output
```

The build retains the tested hook-byte, prefix-change, workspace/ELF, instruction-boundary and arithmetic checks. It creates a private image only in the supplied fresh output directory, verifies the tested SHA256 `b4b1196c961533ac42b9604c945f3932097dfba80347857e431c03a5c6759f20`, and exits2 for a different image. A matching hash is offline reproduction of the image bytes; it is not new hardware validation. The ROM was an earlier analysis identity check, not a compile/link input, and is unnecessary here.

## Linux source reconstruction

Provide Raspberry Pi Linux source at commit `60ea684a8ace97bb0db1a16e20753bdd6ab371ff`. Obtain that complete tree and its notices from [the upstream repository](https://github.com/raspberrypi/linux/tree/60ea684a8ace97bb0db1a16e20753bdd6ab371ff) under its applicable terms. Git is required to apply the patch. The recipe checks every retained pristine source hash before copying or patching.

```text
python driver/prepare.py --kernel-source /path/to/linux --out /path/to/fresh-driver-source
```

The output must match all96 tested source hashes. The logical patch uses LF; the wrapper restores the recorded CRLF form for six captured files before hash checking. This preserves exact historical source bytes without bloating the patch with newline-only changes. Generated `pi5_owned_contract.h` is fixed to the tested b4b ABI36 image, not a general contract for other builds. The native builder emits its recorded ASCII/CRLF bytes explicitly on every host platform. After a native rebuild, compare its generated contract byte-for-byte with `driver/additions/brcmfmac/pi5_owned_contract.h`.

On a separate matching aarch64 build environment with Linux6.18.39+rpt-rpi-2712 headers/configuration/Module.symvers and Debian GCC 14.2.0-19:

```text
make -C /lib/modules/6.18.39+rpt-rpi-2712/build M=/absolute/path/to/fresh-driver-source -j2 V=1 modules
```

A fresh unprivileged compile from this source-only reconstruction succeeded in 19.058 seconds using those exact headers and GCC 14.2.0-19. The complete module SHA matches the historical tested d437 binary, and all 45 allocated/relocation sections, metadata and native fingerprint pass comparison. Nothing was installed. See driver/compile-receipt.json. The tested module SHA256 is `d4374b5607ee43483911702da18516f3b60ecd4385df2edbe7ceee39729412a0`, srcversion9454D5850E6A2119D00CB39, buildID7adf30436c15d6ccaab46fce2a16c9f12fef1d5f. Debug paths, compiler/header configuration and module-version inputs can change the rebuilt module's bytes, so hash equality is not promised from arbitrary build paths.

Do not run modules_install, replace firmware, unload a driver or replay an old capture worker using this package. A future public acquisition runner needs its own fresh-session admission, recovery and health review. Source reconstruction and exact native rebuilding are useful independently of that remaining operational work.

## Bounded validation of a fresh module build

Use an unprivileged fresh build directory and the matching existing headers. Check `uname -r`, the header symlink, `aarch64-linux-gnu-gcc-14 --version`, make and Git availability. A source reconstruction from the exact pinned baseline must pass before compilation. Preserve logs and outputs; do not install the result. No full workspace archive is needed: stage only this source-only package and reader-supplied pinned baseline files, then retain the 96 reconstructed files listed in expected-source.json.

```text
make -C /lib/modules/6.18.39+rpt-rpi-2712/build M=/absolute/path/to/fresh-driver-source -j2 V=1 modules
python driver/compare_module.py /path/to/rebuilt/brcmfmac/brcmfmac.ko
```

The comparator checks all tested allocated sections and relocation sections, exact vermagic/srcversion/licence declarations, and presence of the ELF-derived native fingerprint. It ignores debug paths and the build-id note and also reports whether the full historical SHA matches. Passing this check establishes comparison with tested executable/data bytes; it does not constitute a new capture or healthy-device test. The separately bound fresh compile receipt records `module_compiled_by_new_wrapper:true`; compilation equality does not validate device loading or acquisition.

The corrected current comparator separately validates the preserved rebuilt module's ELF class, little-endian encoding, relocatable type and AArch64 machine identity, all 45 allocated/relocation sections and exact historical SHA. See driver/architecture-validation-receipt.json. This is a new offline identity/comparison check of the previously compiled file; it is not a new compilation, installation or hardware run. The original driver/compile-receipt.json retains its historical comparator binding.
