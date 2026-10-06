# Inspecting the STEP0 RF decisions

The public [predeclared plan](../../evidence/rf-step0/plan.json) and [fitted values](../../evidence/rf-step0/fitted-values.json) retain all 80 selected ON chunk fits and the four matched OFF summaries for each ON window. Each 16,384-word chunk has its fitted complex coefficient, refined frequency, nuisance-line fit, residual, descriptive floor and explicit neighbor-diagnostic availability. The 40 unavailable optional neighbor medians are null, not zero.

From the package root, run with Python 3.10 or later:

```text
python src/rf_step0/decisions.py
python -m unittest discover -s tests -p test_rf_decisions.py
```

The standard-library decision reproducer checks derivative hashes, recomputes all 80 chunk decisions, window frequency IQRs, interwindow drift and the minimum ON/adjacent-OFF95 amplitude ratio 26.733026989053336. Its [provenance](../../evidence/rf-step0/provenance.json) binds the original frozen plan/method/strict response by hash and describes the allowlist transformation.

OFF95 percentiles are supplied saved fit summaries. Individual OFF fit rows were not retained in the selected response; the public tool cannot independently recalculate those percentiles. The tool also does not refit the original withheld waveforms, validate source timing or repeat the hardware/frame/health audit. Published coefficients and summaries permit inspection of the acceptance arithmetic, not independent verification of the original measurements.

[method.py](method.py) provides the exact eight mathematical functions extracted from the frozen pre-acquisition analysis, without private paths, imports or operational controllers. It requires NumPy, while the decision reproducer does not. `analyse_ON(chunks)` accepts twenty complex arrays of 16,384 words in the documented low-real/high-imag convention; `project(y, frequencies)` also defines the matched OFF fit. Window selection and source timing follow the exported plan and still require appropriate supplied data. The unchanged frozen `project` yields NaN for the optional median of no eligible neighbor projections. `strict_project` exposes that diagnostic as null/None with the exclusion count; it leaves the finite operative conditional floor unchanged.

[requirements.txt](requirements.txt) pins NumPy 2.3.5, the available version used for the portable method's small deterministic direct-least-squares checks. It is a tested dependency for this extracted method, not a claim that the original waveform fit environment used that version. The fitted-value decision check needs no installed NumPy.

The least-squares scales/floors are descriptive. IID, stationarity and confidence coverage were not established. Chunks in one burst are dependent. The test covers two bounded source bursts during one five-minute receive stream; it does not prove a five-minute continuous transmitter, calibrated frequency/power, raw-to-filtered attenuation or comprehensive anti-alias rejection. The measured line lies outside the earlier wanted +/-0.048 cycles/output interval.
