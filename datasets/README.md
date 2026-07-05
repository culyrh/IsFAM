# IsFAM AI Evaluation Datasets

이 폴더는 모델 평가용 로컬 음성 데이터를 넣는 곳입니다.

음성 파일은 개인정보와 용량 문제 때문에 Git에 올리지 않습니다. `.gitignore`가 `*.wav`, `*.mp3`, `*.m4a` 파일을 무시합니다.

## Anti-Spoofing

```text
datasets/anti_spoofing/
  real/
    real_001.wav
  fake/
    fake_001.wav
```

- `real`: 실제 사람 음성
- `fake`: TTS, voice conversion, deepfake 등 AI 생성 또는 합성 음성

## Speaker Verification

```text
datasets/speaker_verification/
  mother/
    enroll_001.wav
    test_001.wav
  unknown/
    unknown_001.wav
  pairs.csv
```

`pairs.csv` 형식:

```csv
audio_file_1,audio_file_2,label
mother/enroll_001.wav,mother/test_001.wav,same
mother/enroll_001.wav,unknown/unknown_001.wav,different
```

- `same`: 같은 사람 음성 쌍
- `different`: 다른 사람 음성 쌍
