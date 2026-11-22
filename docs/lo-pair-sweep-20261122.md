# Seven tracking pairs in the 5 and 6 GHz tuning sweep

Seven of eleven tested pairs on the Raspberry Pi 5 onboard receiver tracked a fixed signal when the requested local oscillator (LO) moved up 1 MHz. The lowest and highest passing settings were 4,748 and 6,474 MHz, an endpoint separation of 1,726 MHz. The sweep included no intermediate setting between 4,999 and 5,998 MHz. Continuous coverage remains unverified.

| Requested LO pair (MHz) | Peak shift (MHz) | Peak above spectral median, A / B (dB) | Source tracked |
|---|---|---|---|
| 4,598 / 4,599 | +0.0439 | 39.86 / 41.52 | No |
| 4,698 / 4,699 | +0.0415 | 41.49 / 44.47 | No |
| 4,748 / 4,749 | +1.0877 | 55.00 / 52.70 | Yes |
| 4,798 / 4,799 | +1.0755 | 54.53 / 53.60 | Yes |
| 4,898 / 4,899 | +1.0535 | 64.64 / 64.37 | Yes |
| 4,998 / 4,999 | +1.0327 | 61.83 / 61.78 | Yes |
| 5,998 / 5,999 | +0.9985 | 48.93 / 49.06 | Yes |
| 6,398 / 6,399 | +0.9985 | 36.85 / 36.14 | Yes |
| 6,473 / 6,474 | +0.9985 | 38.33 / 38.33 | Yes |
| 6,548 / 6,549 | -0.0097 | 20.96 / 19.32 | No |
| 6,698 / 6,699 | +0.0110 | 8.99 / 11.24 | No |

Each setting contributed eight bursts of 16,000 complex samples. We removed the mean, applied a Hann window and averaged power across 16,384-point FFTs at the nominal 20 MSPS rate. We excluded 32 bins around DC when selecting the strongest peak. A passing pair had a positive shift within 0.15 MHz of 1 MHz and both peaks at least 12 dB above their spectral medians. This is a differential tracking measurement. The peak-height metric uses a per-bin reference.

The measured lower transition lies between 4,699 and 4,748 MHz on the receiver LO axis. The upper transition lies between 6,474 and 6,548 MHz. The 6,473/6,474 MHz pair used the second harmonic of a 3,237.5 MHz generator setting. From 4,748 to 4,999 MHz the shifts exceeded 1 MHz at the nominal sample rate. Their cause remains unresolved.

Adding the earlier 780.5 MHz low-band endpoint estimate to 1,726 MHz gives 2,506.5 MHz across two separate endpoint spans. Neither instantaneous bandwidth nor continuous tuning coverage was measured by that addition.

[Download the aggregate measurements](../evidence/lo-pair-sweep-20261122.json).
