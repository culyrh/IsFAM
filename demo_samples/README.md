# IsFAM Demo Samples

비용이 들지 않는 웹 데모용 로컬 샘플 폴더입니다.

```text
demo_samples/
  real/
    real_001.wav
  fake/
    fake_001.wav
```

- `real`: 실제 사람 녹음 샘플
- `fake`: 사전에 준비한 AI/TTS/합성 음성 샘플

사용자에게 업로드받은 가족 목소리로 딥보이스를 즉석 생성하지 않습니다. 데모는 이 폴더에 미리 넣어둔 샘플을 랜덤 재생하고, 사용자의 판단과 IsFAM AI 판단을 비교합니다.

지원 확장자는 서버 설정의 `ISFAM_ALLOWED_AUDIO_EXTENSIONS`를 따릅니다. 기본값은 `wav`, `mp3`, `m4a`입니다.
