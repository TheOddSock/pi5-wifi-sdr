# Source availability and exact build scope

The source package separately supplies the preserved historical ABI36 b4b/d437
recipe and this source-only ABI37 clock-read revision. With the pinned inputs
and toolchains, the standalone recipes reproduce the complete 652800-byte native
image and 656600-byte driver module exactly. The native image SHA is
58a9740679366ddb1007bf79abe983aca4d4ad9458c841af33091052e163b62e;
the module SHA is
44c21fc659f3182655757a2b6dfd3c969fd713dda03b910863e1925de69d01be.
All 96 driver source hashes and all 45 allocated/relocation sections match.
The standalone driver build ran unprivileged in 19.253556852 seconds, without
installation or changes to the boot, loaded identity or selected original.

This establishes exact software-build reproduction in the documented environment.
Native ELF debug/symbol bytes differ with source/output paths although the
composed image is exact. Other toolchains/paths/header configurations are not
promised identical module bytes. Neither build recipe installs a receiver or
provides an accepted hour measurement, calibrated RF bandwidth, general packet
decoder or unlimited reliability. Manufacturer inputs, private recordings and
operational acquisition/recovery controllers are excluded.
