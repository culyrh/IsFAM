# IsFAM Evaluation Audio

Put evaluation audio files here. These files are for scoring and threshold tuning, not model training.

Recommended format:

```text
datasets/eval/
  family_real/
    mom_register_01.wav
    mom_register_02.wav
    mom_register_03.wav
    mom_test_01.wav
  non_family_real/
    stranger_test_01.wav
  family_deepvoice/
    mom_deepvoice_01.wav
  ai_voice/
    tts_test_01.wav
  noisy_call/
    mom_noisy_test_01.wav
```

Use the same person name in filenames when a file belongs to the same family member. Files with `register` in the name should be registered as family voiceprints before evaluating the `test`, `deepvoice`, or `noisy` files.

Register the current `family_real/*_register_*` files into the local DB:

```bash
.venv/bin/python scripts/register_eval_family.py
```

Preview without loading AI models or writing the DB:

```bash
.venv/bin/python scripts/register_eval_family.py --dry-run
```

Evaluate non-register files and write `reports/isfam_eval_results.csv`:

```bash
.venv/bin/python scripts/evaluate_isfam_eval.py
```
