# Family Voiceprint Evaluation

This report uses only current `datasets/eval/family_real` audio files.
It measures family voiceprint separability, not deepfake detection accuracy.

## Dataset

- files: 10
- speakers: daughter, mom
- same-speaker pairs: 20
- different-speaker pairs: 25

## Similarity Distribution

- same mean: 0.7898
- same min: 0.6676
- same max: 0.8782
- different mean: 0.4311
- different min: 0.3651
- different max: 0.5021
- separation gap `(min same - max different)`: 0.1655

## Recommended Threshold

- recommended threshold: 0.65
- accuracy at threshold: 1.0
- false accept rate: 0.0
- false reject rate: 0.0
- same-speaker safety margin `(min same - threshold)`: 0.0176
- different-speaker safety margin `(threshold - max different)`: 0.1479
- confidence grade: high

The recommendation prefers zero false-accept thresholds and then chooses the strictest threshold among the best candidates.

## Leave-One-Out Identification

- accuracy: 1.0
- correct: 10/10
- mean top-1 margin: 0.0269
- min top-1 margin: 0.0013

## Sample Quality

- samples needing review: 2

- mom_register_03.m4a: same-speaker margin is narrow (min_same=0.6676, max_diff=0.4986)
- mom_register_05.m4a: same-speaker margin is narrow (min_same=0.6676, max_diff=0.5021)

## Interpretation

Current family samples are separable in this dataset.

This report cannot claim deepfake detection accuracy because no fake-family or AI-voice evaluation files are included.
