# ABI36 source-only build package

This package contains source and patches for the tested BCM43455c0 ABI36 twin6 receive stream. Original project code uses GPL-2.0-or-later and documentation uses CC BY 4.0 under the outer licence grant; existing upstream terms remain applicable. The recipe builds software without installing it and is separate from all consumed hardware sessions.

The native builder has locally reproduced the **exact tested b4b image**, using a reader-supplied pristine MFG image and xPack GCC9.3.1. No ROM blob is linked or copied. The driver recipe reconstructs the exact tested d437 source tree from a pinned reader-supplied kernel source tree, a seven-file patch (six driver files plus the Kbuild wrapper), and twelve small added headers/fragments. It does not bundle the Linux source tree or a module binary.

Neither this directory nor its allowlisted source package contains vendor firmware, ROM, generated images/modules, ambient samples, network profiles, deployment workers or historical archives. Local rebuild products and private test fixtures are retained separately outside this directory.

Read [build instructions](BUILD.md), [rights and dependencies](RIGHTS.md), [exact input/toolchain identities](dependencies.json), [component map](component-rights.csv) and [the manifest](manifest.json). Original project code is covered by the outer GPL-2.0-or-later grant and exact component map. Included Linux context retains its upstream file licence; the kernel's whole-work and module obligations remain separate. The build recipe does not install or operate the hardware.

A fresh unprivileged reconstruction and compilation reproduces the complete tested driver SHA as well as its 45 allocated/relocation sections. This is exact software-build reproduction; the private acquisition controller is withheld, and no installation or new radio experiment occurred.
