# Limits of the demonstrated receiver

The demonstrated result is sustained reduced-rate selected complex output. The following properties require further evidence.

This is an experimental sample-streaming capability, with an audited one-hour recording. The chip's diagnostic collector already existed; the demonstrated contribution is sustained, checked export to Linux on the exact BCM43455c0 configuration. ESP-SDR's sample-access and continuous-streaming work are prior related implementations. No first-ever access claim is established. Sample access does not yet establish a practical general-purpose SDR receiver; see the [project explanation](../README.md#what-this-project-achieves).

- Capture mode 17 is associated with the vendor-labelled `rx_filt_1core` receive path. Its exact ordering relative to all internal filters and corrections is uncharacterised; bare-ADC access is not established.
- Each ordinary output retains one of sixteen input positions. The six-input kernel combines six values before advancing sixteen positions. Complete input export is not demonstrated.
- Firmware extends a modulo writer pointer with timing and lag checks. An independent absolute generation counter is absent, leaving full-lap and unmodelled-pause uncertainty.
- Sample rates and frequency axes are nominal. Clock accuracy, RF tuning error, physical I/Q orientation, converter resolution and dynamic range are uncalibrated.
- The first-stage six-input filter has weak nearby-alias rejection. The sparse comb has selective odd-alias notches and leaves other aliases exposed. Host filtering cannot reverse earlier folding.
- The separately audited one-hour recording extends the twin6 duration envelope; older five-minute runs retain their own settings and reader contracts. Reliability beyond that tested hour, systematic CPU/storage/RF stress, other Pi models and other firmware revisions remain unestablished. Raw-position rollover is observed; selected-word-counter rollover and absolute physical-input continuity remain unproved.
- Healthy Ethernet management does not establish sample forwarding over Ethernet. Offline host DSP speed does not establish real-time Pi DSP.
- This prototype requires privileged custom firmware/driver work. It establishes no privilege bypass or security vulnerability.
- The full ambient recordings are private. Public aggregate checks and synthetic fixtures are narrower than a repeat of the full historical audits.
- Exact device source builds are reproducible from the included recipe and reader-supplied inputs. The operational installation/acquisition/recovery controller is not included. Reader-supplied manufacturer inputs remain subject to their own terms.

No broad first-in-the-world, calibrated bandwidth, peer-review or external-replication claim is made. Successful finite validation of earlier radio waveforms is kept separate from long-stream RF characterisation.


The five-minute STEP0 result establishes source correlation during two bounded bursts, not known-signal coverage of every word or moment. The one-hour and ten-minute recordings are passive. Twelve historical finite Wi-Fi decodes establish neither a packet-error rate nor continuous decoding on the reduced-rate stream.
