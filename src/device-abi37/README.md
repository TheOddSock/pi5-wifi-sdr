# ABI37 source-only build package

This package supplies the BCM43455c0 ABI37 coherent TSF
reader, first rejected-observation logging and its matching driver contract.
The separate historical ABI36 b4b/d437 source package remains preserved.
The current native target SHA is 58a9740679366ddb1007bf79abe983aca4d4ad9458c841af33091052e163b62e.
The 96-file driver target source matches the compiled 44c21fc659f3182655757a2b6dfd3c969fd713dda03b910863e1925de69d01be
module's source snapshot. Standalone recipe native and module rebuild results
must be read from the separate reviewed receipts; their source availability
alone does not establish hardware success or an accepted hour.

Read [BUILD.md](BUILD.md), [RIGHTS.md](RIGHTS.md), [INTEGRATION.md](INTEGRATION.md),
[dependencies.json](dependencies.json) and the exact [file map](component-licences.csv).
The package excludes manufacturer images/ROM, kernel/header bulk, modules,
recordings, network profiles and acquisition/recovery controllers. It has no
installation command. Original code uses GPL-2.0-or-later; original documentation uses CC BY 4.0. Existing upstream terms remain applicable.
