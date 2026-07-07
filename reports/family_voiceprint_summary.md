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

## Best Threshold In Sweep

- threshold: 0.55
- accuracy: 1.0
- false accept rate: 0.0
- false reject rate: 0.0

## Leave-One-Out Identification

- accuracy: 1.0
- correct: 10/10
- mean top-1 margin: 0.0269
- min top-1 margin: 0.0013

## Interpretation

Current family samples are separable in this dataset.
