# Hardware integration boundary

This package rebuilds the tested software. It does not install a receiver or
contain the tested full acquisition controller. A compatible recording supplied
separately can be audited with the report package's frame verifier.

The tested integration uses Raspberry Pi 5 BCM43455c0, matching 6.18.39+rpt-rpi-2712
kernel/module configuration, the exact b4b image/d437 module and ABI36 contract.
The board's ordinary Wi-Fi operation is changed. Ethernet is the management path.
Chip names, firmware version strings and a successful compile alone do not admit
another device or firmware revision.

Before deployment, independently preserve original firmware, NVRAM, modules,
selected paths and boot/service state, and prepare a tested recovery path. Check
the exact chip, image, contract, loaded module and reader identities. Do not use a
consumed historical session or replay its workers. Installation/recovery commands
are intentionally absent because the private controller's dependencies and host
paths are not part of this source package.

The demonstrated acquisition contract requires a fresh exclusively admitted
capture owner, a reader initialized against the exact owned-RAM descriptor,
bounded frame/storage quotas, sequence/metadata/FNV checks, timely lease renewal,
native watchdog service and a bounded recording queue. Capture control remains
active while the concurrent reader exports committed slots. Close requests STOP;
the operator must collect the genuine vendor reply and verify idle state, one
accounted unread suffix, newest retained tail, full native pair restoration and
device health. Firmware publication checks do not establish absolute input
continuity, calibrated RF bandwidth or unlimited reliability.

A public operational runner is a distinct next milestone. It must replace the
private freshness/health inputs with documented reader-owned configuration,
preserve original/rollback state, refuse incompatible identities and stale
sessions, implement the reviewed control/reader lifecycle, and be validated on
fresh hardware sessions before being described as a runnable experiment. The
current findings release discloses the mechanism and exactly rebuildable source
while stating this integration gap explicitly.
