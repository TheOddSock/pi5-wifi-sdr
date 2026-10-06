# Rights and dependency boundaries

Original native append, Python wrappers and new driver fragments use GPL-2.0-or-later under the outer licence grant. Original documentation uses CC BY 4.0. The release component map supplies the exact assignments. Existing upstream copyright notices and terms remain applicable.

The six Linux files changed by the patch retain their pinned upstream ISC identifiers and copyright notices. Unchanged Linux source is supplied by the reader, not bundled. The included ISC/COPYING/GPL2 texts are copied from the exact pinned upstream tree with download hashes. [Kernel licence rules](https://www.kernel.org/doc/html/latest/process/license-rules.html) distinguish file-specific licences from the kernel as a whole; [SPDX ISC](https://spdx.org/licenses/ISC.html) identifies the licence's notice conditions. This map is a factual inventory, not clearance of the new contributions or a legal opinion about derivative obligations. The historical module declares DualBSD/GPL, separately recorded in dependencies.json.

The proprietary MFG image and ROM are excluded. Reader-supplied MFG bytes remain hash-bound inputs, and their actual acquisition/use terms must be checked independently. Reverse-engineered function addresses and new append logic do not grant permission to redistribute the manufacturer image. This build links no copied ROM body and requires no ROM file.

Toolchain executables, Python dependencies, kernel headers/generated files and full Linux source are excluded. The reader obtains those from their respective distributors, retains notices, and supplies compatible versions. This avoids repackaging them, while retaining their technical build dependence.


This source-only distribution supports offline build reproduction. A public installation/acquisition/recovery controller is not included.
