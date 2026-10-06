# Hardware integration boundary

This source-only package does not install a receiver or include an operational
acquisition/recovery controller. ABI37 is the implementation used for the accepted passive one-hour recording.
Source-build equality and hardware acceptance are separate results; the latter
is documented in the release evidence registry. Preserve original evidence and
rollback state when planning any new hardware work.

Fresh deployment requires independently reviewed chip/image/module/contract
identities, native GEO1 before GO, finite RAM/storage/timing bounds, one admitted
capture owner, metadata/FNV/sequence checks, lease/watchdog service, genuine STOP,
newest-tail/full-pair restoration and retained device health. Never replay a
consumed historical session or bypass admission. RF filtering, clock calibration,
general continuous packet decoding and unlimited reliability remain unproved.
