# IsFAM Speaker Verification Server

IsFAM 1차 서버는 가족 사칭형 AI 보이스피싱 방지를 위한 **AI 모델 기반 화자 인증(Speaker Verification) API**입니다. 두 음성 파일을 업로드하면 SpeechBrain의 pretrained ECAPA-TDNN 모델로 speaker embedding을 추출하고 cosine similarity를 계산해 같은 화자인지 판별합니다.

## 기술 스택

- Python
- FastAPI
- SpeechBrain
- Hugging Face Transformers
- PyTorch / Torchaudio
- Speaker verification model: `speechbrain/spkrec-ecapa-voxceleb`
- Anti-spoofing model: `Vansh180/deepfake-audio-wav2vec2`

## 프로젝트 구조

```text
app/
  main.py
  api/routes/anti_spoofing.py
  api/routes/family.py
  api/routes/voice.py
  api/routes/voice_session.py
  core/config.py
  db/session.py
  repositories/family_repository.py
  repositories/voice_session_repository.py
  schemas/anti_spoofing.py
  schemas/family.py
  schemas/voice.py
  schemas/voice_session.py
  services/model_provider.py
  services/anti_spoofing_service.py
  services/speaker_service.py
  services/voice_session_service.py
  services/voiceprint_service.py
  utils/audio.py
datasets/
  anti_spoofing/real/
  anti_spoofing/fake/
  speaker_verification/
scripts/
  evaluate_anti_spoofing.py
  evaluate_speaker_verification.py
reports/
mobile/
  index.html
  src/main.js
  src/styles.css
  android/
requirements.txt
README.md
.gitignore
```

## 설치 방법

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

mp3, m4a 디코딩은 실행 환경의 torchaudio/FFmpeg 지원 상태에 영향을 받습니다. 이 서버는 먼저 torchaudio로 디코딩을 시도하고, 실패하면 로컬 FFmpeg 명령어로 16kHz mono wav 변환을 다시 시도합니다. macOS에서 m4a 또는 일부 mp3가 디코딩되지 않으면 FFmpeg 설치가 필요합니다.

```bash
brew install ffmpeg
```

## 실행 방법

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

처음 `/api/v1/voice/compare` 또는 `/api/v1/voice/verify-family` 요청이 들어오면 SpeechBrain이 Hugging Face에서 speaker verification 모델 파일을 `pretrained_models/spkrec-ecapa-voxceleb` 경로로 자동 다운로드합니다. 처음 `/api/v1/anti-spoofing/detect` 또는 `/api/v1/voice/verify-family-secure` 요청이 들어오면 Hugging Face Transformers가 anti-spoofing 모델 파일을 `pretrained_models/deepfake-audio-wav2vec2` 경로로 자동 다운로드합니다. 첫 요청은 다운로드 때문에 시간이 오래 걸릴 수 있습니다.

서버 시작 시 SQLite DB 파일이 자동 생성됩니다.

```text
data/isfam.sqlite3
```

이 DB에는 가족 이름, 관계, 모델명, speaker embedding BLOB이 저장됩니다. API 응답에는 embedding을 노출하지 않습니다.

## Android 시연 앱

`mobile/` 폴더에는 Capacitor 기반 Android 시연 앱이 있습니다. AI 모델은 앱에서 돌지 않고 FastAPI 서버를 호출합니다.

백엔드 실행:

```bash
cd /Users/leejooho/Desktop/FinNect
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

모바일 앱 설치/실행:

```bash
cd /Users/leejooho/Desktop/FinNect/mobile
npm install
npm run dev
```

브라우저 미리보기:

```text
http://127.0.0.1:5173
```

Android Studio로 열기:

```bash
npm run build
npm run cap:sync
npm run android
```

Android 에뮬레이터에서는 기본 API 주소가 `http://10.0.2.2:8000`입니다. 실제 기기에서는 앱 홈 화면에서 Mac의 같은 Wi-Fi IP 주소로 바꾸면 됩니다.

## API

### Health Check

```bash
curl http://localhost:8000/health
```

응답:

```json
{"status":"ok"}
```

### Voice Compare

```bash
curl -X POST "http://localhost:8000/api/v1/voice/compare" \
  -F "audio_file_1=@/path/to/family_voice.wav" \
  -F "audio_file_2=@/path/to/call_voice.wav"
```

응답 예시:

```json
{
  "similarity": 0.83,
  "threshold": 0.75,
  "is_same_speaker": true,
  "message": "same_speaker",
  "model_name": "speechbrain/spkrec-ecapa-voxceleb"
}
```

### Family Voiceprint Register

가족 음성을 등록하고 voiceprint를 DB에 저장합니다.

```bash
curl -X POST "http://localhost:8000/api/v1/family/register" \
  -F "name=엄마" \
  -F "relation=mother" \
  -F "audio_file=@/path/to/mother_voice.m4a"
```

응답 예시:

```json
{
  "family_id": 1,
  "name": "엄마",
  "relation": "mother",
  "model_name": "speechbrain/spkrec-ecapa-voxceleb",
  "message": "voiceprint_registered"
}
```

DB에는 실제 비교에 필요한 speaker embedding이 저장되지만, 응답에는 보여주지 않습니다.

### Verify Call Voice Against Registered Family

새 통화 음성 1개를 업로드하면 DB에 등록된 모든 가족 voiceprint와 비교합니다.

```bash
curl -X POST "http://localhost:8000/api/v1/voice/verify-family" \
  -F "audio_file=@/path/to/call_voice.m4a"
```

응답 예시:

```json
{
  "is_registered_family": true,
  "best_match": {
    "family_id": 1,
    "name": "엄마",
    "relation": "mother",
    "similarity": 0.86
  },
  "threshold": 0.75,
  "candidates": [
    {
      "family_id": 1,
      "name": "엄마",
      "relation": "mother",
      "similarity": 0.86
    },
    {
      "family_id": 2,
      "name": "아빠",
      "relation": "father",
      "similarity": 0.31
    }
  ],
  "message": "registered_family_matched",
  "model_name": "speechbrain/spkrec-ecapa-voxceleb"
}
```

등록된 가족이 없으면 `best_match`는 `null`, `candidates`는 빈 배열로 반환됩니다.

### Anti-Spoofing Detect

새 음성 1개를 업로드하면 Hugging Face audio classification 모델로 실제 사람 음성인지, spoof/deepfake 의심 음성인지 판별합니다.

```bash
curl -X POST "http://localhost:8000/api/v1/anti-spoofing/detect" \
  -F "audio_file=@/path/to/call_voice.m4a"
```

응답 예시:

```json
{
  "is_spoofed": true,
  "spoof_score": 0.0723,
  "threshold": 0.07,
  "predicted_label": "real",
  "predicted_score": 0.9277,
  "message": "spoof",
  "model_name": "Vansh180/deepfake-audio-wav2vec2",
  "analyzed_segments": 3,
  "max_spoof_segment_index": 1,
  "segment_seconds": 5.0,
  "label_scores": [
    {
      "label": "real",
      "score": 0.9277
    },
    {
      "label": "fake",
      "score": 0.0723
    }
  ]
}
```

### Secure Family Verification

새 통화 음성 1개를 등록 가족 전체와 비교하고, 동시에 딥페이크 탐지도 수행합니다.

```bash
curl -X POST "http://localhost:8000/api/v1/voice/verify-family-secure" \
  -F "audio_file=@/path/to/call_voice.m4a"
```

응답 예시:

```json
{
  "is_trusted": false,
  "final_decision": "spoofed_family_like_voice",
  "family_verification": {
    "is_registered_family": true,
    "best_match": {
      "family_id": 1,
      "name": "엄마",
      "relation": "mother",
      "similarity": 0.86
    },
    "threshold": 0.75,
    "candidates": [
      {
        "family_id": 1,
        "name": "엄마",
        "relation": "mother",
        "similarity": 0.86
      }
    ],
    "message": "registered_family_matched",
    "model_name": "speechbrain/spkrec-ecapa-voxceleb"
  },
  "anti_spoofing": {
    "is_spoofed": true,
    "spoof_score": 0.0723,
    "threshold": 0.07,
    "predicted_label": "real",
    "predicted_score": 0.9277,
    "message": "spoof",
    "model_name": "Vansh180/deepfake-audio-wav2vec2",
    "analyzed_segments": 3,
    "max_spoof_segment_index": 1,
    "segment_seconds": 5.0,
    "label_scores": [
      {
        "label": "real",
        "score": 0.9277
      },
      {
        "label": "fake",
        "score": 0.0723
      }
    ]
  }
}
```

`final_decision` 값은 다음 규칙으로 정해집니다.

- `trusted_family_voice`: 등록 가족과 매칭되고 spoof 의심이 낮음
- `spoofed_family_like_voice`: 등록 가족과 비슷하지만 spoof 의심이 높음
- `unknown_real_voice`: 등록 가족과 매칭되지 않지만 spoof 의심이 낮음
- `spoofed_unknown_voice`: 등록 가족과 매칭되지 않고 spoof 의심이 높음

### Chunk-Based Voice Session

음성을 한 번에 판단하지 않고, 3~5초 단위 청크를 계속 업로드하면서 누적 위험도를 갱신합니다. 나중에 Android 통화 연동을 붙일 때도 앱이 짧은 음성 청크를 이 API로 보내는 구조로 확장할 수 있습니다.

1. 세션 시작:

```bash
curl -X POST "http://localhost:8000/api/v1/voice-sessions/start"
```

응답 예시:

```json
{
  "session_id": "9d4a5f2f4d2b4ab6bb5a7b957b04e51d",
  "status": "active",
  "created_at": "2026-05-11T12:00:00+00:00",
  "updated_at": "2026-05-11T12:00:00+00:00",
  "ended_at": null,
  "chunks_analyzed": 0,
  "total_chunks": 0,
  "analyzable_chunks": 0,
  "skipped_chunks": 0,
  "is_spoofed": false,
  "is_registered_family": false,
  "risk_level": "unknown",
  "message": "no_chunks_analyzed",
  "max_spoof_score": 0.0,
  "max_spoof_chunk_index": null,
  "suspicious_chunks": 0,
  "required_spoof_chunks": 2,
  "strong_spoof_score": 0.35,
  "best_family_match": null,
  "family_match_chunks": 0,
  "required_family_match_chunks": 2,
  "speaker_threshold": 0.75,
  "anti_spoofing_threshold": 0.07
}
```

2. 청크 업로드:

```bash
curl -X POST "http://localhost:8000/api/v1/voice-sessions/9d4a5f2f4d2b4ab6bb5a7b957b04e51d/chunks" \
  -F "chunk_index=0" \
  -F "audio_file=@/path/to/chunk_0.m4a"
```

`chunk_index`는 생략할 수 있습니다. 생략하면 서버가 현재 세션의 다음 번호를 자동으로 붙입니다.

응답 예시:

```json
{
  "session_id": "9d4a5f2f4d2b4ab6bb5a7b957b04e51d",
  "chunk_index": 0,
  "is_analyzable": true,
  "quality": {
    "is_analyzable": true,
    "message": "analyzable",
    "duration_seconds": 4.82,
    "rms_energy": 0.0321,
    "peak_amplitude": 0.41,
    "speech_ratio": 0.76
  },
  "is_trusted_chunk": true,
  "final_decision": "trusted_family_voice",
  "family_verification": {
    "is_registered_family": true,
    "best_match": {
      "family_id": 1,
      "name": "엄마",
      "relation": "mother",
      "similarity": 0.82
    },
    "threshold": 0.75,
    "candidates": [
      {
        "family_id": 1,
        "name": "엄마",
        "relation": "mother",
        "similarity": 0.82
      }
    ],
    "message": "registered_family_matched",
    "model_name": "speechbrain/spkrec-ecapa-voxceleb"
  },
  "anti_spoofing": {
    "is_spoofed": false,
    "spoof_score": 0.02,
    "threshold": 0.07,
    "predicted_label": "real",
    "predicted_score": 0.98,
    "message": "bonafide",
    "model_name": "Vansh180/deepfake-audio-wav2vec2",
    "analyzed_segments": 1,
    "max_spoof_segment_index": 0,
    "segment_seconds": 5.0,
    "label_scores": [
      {
        "label": "real",
        "score": 0.98
      },
      {
        "label": "fake",
        "score": 0.02
      }
    ]
  },
  "rolling_result": {
    "session_id": "9d4a5f2f4d2b4ab6bb5a7b957b04e51d",
    "status": "active",
    "created_at": "2026-05-11T12:00:00+00:00",
    "updated_at": "2026-05-11T12:00:05+00:00",
    "ended_at": null,
    "chunks_analyzed": 1,
    "total_chunks": 1,
    "analyzable_chunks": 1,
    "skipped_chunks": 0,
    "is_spoofed": false,
    "is_registered_family": false,
    "risk_level": "medium",
    "message": "family_match_needs_more_chunks",
    "max_spoof_score": 0.02,
    "max_spoof_chunk_index": 0,
    "suspicious_chunks": 0,
    "required_spoof_chunks": 2,
    "strong_spoof_score": 0.35,
    "best_family_match": {
      "family_id": 1,
      "name": "엄마",
      "relation": "mother",
      "similarity": 0.82
    },
    "family_match_chunks": 1,
    "required_family_match_chunks": 2,
    "speaker_threshold": 0.75,
    "anti_spoofing_threshold": 0.07
  }
}
```

청크가 너무 짧거나, 거의 무음이거나, 말소리 비율이 낮으면 AI 모델 추론 전에 건너뜁니다. 이 경우 `family_verification`과 `anti_spoofing`은 `null`입니다.

```json
{
  "is_analyzable": false,
  "quality": {
    "is_analyzable": false,
    "message": "low_energy_or_silence",
    "duration_seconds": 3.2,
    "rms_energy": 0.0008,
    "peak_amplitude": 0.009,
    "speech_ratio": 0.03
  },
  "final_decision": "low_quality_chunk_skipped",
  "family_verification": null,
  "anti_spoofing": null
}
```

3. 세션 상태 조회:

```bash
curl "http://localhost:8000/api/v1/voice-sessions/9d4a5f2f4d2b4ab6bb5a7b957b04e51d"
```

4. 세션 종료:

```bash
curl -X POST "http://localhost:8000/api/v1/voice-sessions/9d4a5f2f4d2b4ab6bb5a7b957b04e51d/end"
```

`risk_level` 값은 다음 의미입니다.

- `unknown`: 아직 분석한 청크가 없음
- `low`: 등록 가족과 매칭되고 spoof 의심이 낮음
- `medium`: 판단 근거가 아직 부족하거나, 약한 spoof/family 신호가 있어 추가 청크가 필요함
- `high`: spoof 점수가 매우 높거나, spoof 의심 청크가 반복됨

청크 누적 판단은 단일 청크 오판을 줄이기 위해 다음 규칙을 사용합니다.

- 저품질 청크는 `low_quality_chunk_skipped`로 저장하고 AI 판단에서 제외
- `spoof_score >= anti_spoofing_threshold`인 청크가 1개만 있으면 보통 `medium`
- suspicious 청크가 `required_spoof_chunks`개 이상 반복되면 `high`
- `spoof_score >= strong_spoof_score`이면 한 청크만으로도 `high`
- 같은 가족이 `required_family_match_chunks`개 이상 반복 매칭되어야 rolling 결과에서 가족으로 확정

### Family List

등록된 가족 목록을 조회합니다.

```bash
curl "http://localhost:8000/api/v1/family"
```

응답 예시:

```json
{
  "members": [
    {
      "family_id": 1,
      "name": "엄마",
      "relation": "mother",
      "model_name": "speechbrain/spkrec-ecapa-voxceleb"
    }
  ]
}
```

### Family Detail

```bash
curl "http://localhost:8000/api/v1/family/1"
```

응답 예시:

```json
{
  "family_id": 1,
  "name": "엄마",
  "relation": "mother",
  "model_name": "speechbrain/spkrec-ecapa-voxceleb"
}
```

### Family Delete

```bash
curl -X DELETE "http://localhost:8000/api/v1/family/1"
```

응답 예시:

```json
{
  "family_id": 1,
  "message": "family_member_deleted"
}
```

Swagger UI로도 테스트할 수 있습니다.

```text
http://localhost:8000/docs
```

## 설정 변경

설정은 `app/core/config.py`에 모아두었고 환경변수로 덮어쓸 수 있습니다. 환경변수 prefix는 `ISFAM_`입니다.

```bash
ISFAM_SPEAKER_THRESHOLD=0.72 uvicorn app.main:app --reload
ISFAM_MAX_UPLOAD_SIZE_MB=50 uvicorn app.main:app --reload
ISFAM_MIN_AUDIO_SECONDS=1.5 uvicorn app.main:app --reload
ISFAM_DEVICE=cpu uvicorn app.main:app --reload
ISFAM_DATABASE_PATH=data/isfam.sqlite3 uvicorn app.main:app --reload
ISFAM_ANTI_SPOOFING_THRESHOLD=0.07 uvicorn app.main:app --reload
ISFAM_ANTI_SPOOFING_MODEL_NAME=Vansh180/deepfake-audio-wav2vec2 uvicorn app.main:app --reload
ISFAM_ANTI_SPOOFING_WINDOW_SECONDS=5.0 uvicorn app.main:app --reload
ISFAM_ANTI_SPOOFING_HOP_SECONDS=2.5 uvicorn app.main:app --reload
ISFAM_VOICE_SESSION_REPEATED_SPOOF_CHUNKS=2 uvicorn app.main:app --reload
ISFAM_VOICE_SESSION_STRONG_SPOOF_SCORE=0.35 uvicorn app.main:app --reload
ISFAM_VOICE_SESSION_FAMILY_CONFIRM_CHUNKS=2 uvicorn app.main:app --reload
```

주요 설정:

- `speaker_threshold`: 같은 화자로 판단할 cosine similarity 기준값입니다. 기본값은 `0.75`입니다.
- `max_upload_size_mb`: 업로드 파일당 최대 크기입니다. 기본값은 `25MB`입니다.
- `min_audio_seconds`: 너무 짧은 음성을 거부하기 위한 최소 길이입니다. 기본값은 `1.0초`입니다.
- `target_sample_rate`: 모델 입력용 샘플레이트입니다. 기본값은 `16000Hz`입니다.
- `device`: 기본값은 `cpu`입니다. CUDA 서버에서는 `cuda` 또는 `auto`로 바꿀 수 있습니다.
- `database_path`: 가족 voiceprint 저장용 SQLite DB 경로입니다. 기본값은 `data/isfam.sqlite3`입니다.
- `anti_spoofing_model_name`: Hugging Face anti-spoofing audio classification 모델명입니다. 기본값은 `Vansh180/deepfake-audio-wav2vec2`입니다.
- `anti_spoofing_threshold`: spoof로 판단할 score 기준값입니다. 기본값은 `0.07`입니다. 낮을수록 더 민감하지만 정상 음성을 spoof로 오판할 수 있습니다.
- `anti_spoofing_spoof_labels`: spoof score에 합산할 모델 label 목록입니다. 기본값은 `spoof,fake,deepfake,synthetic,generated,label_1`입니다.
- `anti_spoofing_max_audio_seconds`: anti-spoofing 모델이 분석할 최대 음성 길이입니다. 기본값은 `60초`입니다.
- `anti_spoofing_window_seconds`: anti-spoofing 모델이 한 번에 분석하는 구간 길이입니다. 기본값은 `5초`입니다.
- `anti_spoofing_hop_seconds`: anti-spoofing 구간을 이동하는 간격입니다. 기본값은 `2.5초`입니다.
- `voice_session_min_analyzable_seconds`: 청크 세션에서 AI 분석을 수행할 최소 길이입니다. 기본값은 `2.0초`입니다.
- `voice_session_min_rms_energy`: 무음/저음량 청크를 제외하기 위한 RMS 기준값입니다. 기본값은 `0.005`입니다.
- `voice_session_min_speech_ratio`: 청크 안에서 말소리로 볼 만한 프레임의 최소 비율입니다. 기본값은 `0.25`입니다.
- `voice_session_repeated_spoof_chunks`: rolling 결과를 spoof로 확정하기 위해 필요한 suspicious 청크 수입니다. 기본값은 `2`입니다.
- `voice_session_strong_spoof_score`: 한 청크만으로도 high risk로 올릴 강한 spoof score 기준값입니다. 기본값은 `0.35`입니다.
- `voice_session_family_confirm_chunks`: rolling 결과에서 등록 가족으로 확정하기 위해 필요한 반복 매칭 청크 수입니다. 기본값은 `2`입니다.

## 모델 설명

이 서버는 화자 인증에는 SpeechBrain의 `speechbrain/spkrec-ecapa-voxceleb` pretrained 모델을 사용합니다. 이 모델은 VoxCeleb 데이터셋으로 학습된 ECAPA-TDNN 기반 speaker verification 모델입니다.

딥페이크 탐지에는 Hugging Face의 `Vansh180/deepfake-audio-wav2vec2` audio classification 모델을 사용합니다. 이 모델은 `facebook/wav2vec2-base` 기반으로 fine-tuning된 real/spoof speech 분류 모델이며, 현재 모델 config 기준 label은 `real`과 `fake`입니다.

처리 흐름:

1. 업로드된 `wav`, `mp3`, `m4a` 파일을 임시 파일로 저장합니다.
2. torchaudio로 디코딩합니다. torchaudio가 m4a/mp3를 읽지 못하면 FFmpeg CLI fallback으로 wav 변환을 시도합니다.
3. mono 채널로 변환하고 16kHz로 resampling합니다.
4. 표준 wav 임시 파일로 저장합니다.
5. SpeechBrain `EncoderClassifier.encode_batch()`로 speaker embedding을 추출합니다.
6. 두 embedding 사이의 cosine similarity를 계산합니다.
7. `similarity >= threshold`이면 `same_speaker`, 아니면 `different_speaker`를 반환합니다.

가족 voiceprint 등록 흐름:

1. `POST /api/v1/family/register`로 이름, 관계, 음성 파일을 업로드합니다.
2. 음성을 16kHz mono wav로 변환합니다.
3. SpeechBrain `EncoderClassifier.encode_batch()`로 speaker embedding을 추출합니다.
4. embedding을 float32 bytes로 직렬화합니다.
5. SQLite `family_members` 테이블에 `id`, `name`, `relation`, `embedding`, `model_name`을 저장합니다.
6. API 응답에는 `embedding`을 제외한 metadata만 반환합니다.

등록 가족 전체 비교 흐름:

1. `POST /api/v1/voice/verify-family`로 새 통화 음성 파일을 업로드합니다.
2. 통화 음성을 16kHz mono wav로 변환합니다.
3. SpeechBrain 모델로 통화 음성 embedding을 추출합니다.
4. SQLite에 저장된 모든 가족 embedding을 불러옵니다.
5. 통화 음성 embedding과 각 가족 embedding의 cosine similarity를 계산합니다.
6. similarity가 가장 높은 가족을 `best_match`로 반환합니다.
7. `best_match.similarity >= threshold`이면 등록 가족으로 판단합니다.

딥페이크 탐지 흐름:

1. `POST /api/v1/anti-spoofing/detect`로 새 음성 파일을 업로드합니다.
2. 음성을 16kHz mono wav로 변환합니다.
3. 음성을 5초 구간으로 나누고 2.5초 간격으로 겹쳐서 분석합니다.
4. 각 구간마다 Hugging Face `AutoFeatureExtractor`로 모델 입력을 만듭니다.
5. `AutoModelForAudioClassification`으로 label별 확률을 계산합니다.
6. `spoof`, `fake`, `label_1` 등 config에 등록된 label 확률을 합산해 구간별 `spoof_score`를 만듭니다.
7. 모든 구간 중 가장 높은 `spoof_score`를 최종 `spoof_score`로 사용합니다.
8. `spoof_score >= anti_spoofing_threshold`이면 spoof/deepfake 의심 음성으로 판단합니다.

통합 보안 검증 흐름:

1. `POST /api/v1/voice/verify-family-secure`로 새 통화 음성을 업로드합니다.
2. 등록 가족 전체 비교를 수행합니다.
3. anti-spoofing 탐지를 수행합니다.
4. 가족 매칭 여부와 spoof 여부를 합쳐 `final_decision`을 반환합니다.

청크 기반 연속 분석 흐름:

1. `POST /api/v1/voice-sessions/start`로 세션을 생성합니다.
2. `POST /api/v1/voice-sessions/{session_id}/chunks`로 3~5초 단위 음성을 반복 업로드합니다.
3. 길이, RMS 에너지, speech ratio를 계산해 저품질 청크를 먼저 제외합니다.
4. 분석 가능한 청크에만 등록 가족 전체 비교와 anti-spoofing 탐지를 수행합니다.
5. `voice_session_chunks` 테이블에 청크별 품질 지표와 판단 결과를 저장합니다.
6. spoof 의심 청크 반복 여부와 가족 매칭 반복 여부를 기준으로 rolling result를 갱신합니다.
7. `GET /api/v1/voice-sessions/{session_id}`로 현재까지의 누적 위험도를 조회합니다.
8. 분석이 끝나면 `POST /api/v1/voice-sessions/{session_id}/end`로 세션을 종료합니다.

SpeechBrain 모델 카드에 따르면 해당 모델은 speaker embedding 추출과 cosine similarity 기반 speaker verification에 사용할 수 있으며, 입력 음성은 16kHz single-channel 기준으로 학습되었습니다.

참고:

- https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb
- https://huggingface.co/Vansh180/deepfake-audio-wav2vec2
- https://speechbrain.readthedocs.io/en/stable/API/speechbrain.inference.classifiers.html
- https://huggingface.co/docs/transformers/tasks/audio_classification

## AI 모델 디벨롭 / 평가

모델을 제대로 개선하려면 단일 음성 결과만 보는 것이 아니라, 여러 테스트 파일에 대해 `정답 label`, `모델 점수`, `threshold별 정확도`를 CSV로 쌓아야 합니다. 이 프로젝트에는 그 작업을 위한 평가 스크립트가 포함되어 있습니다.

평가용 음성 파일은 Git에 올리지 않습니다. `.gitignore`가 `*.wav`, `*.mp3`, `*.m4a`를 무시하므로 로컬에서만 관리하면 됩니다.

### Anti-Spoofing 평가 데이터 준비

```text
datasets/anti_spoofing/
  real/
    real_001.wav
    real_002.m4a
  fake/
    fake_001.wav
    fake_002.m4a
```

- `real`: 실제 사람 음성
- `fake`: TTS, voice conversion, deepfake 등 AI 생성/합성 음성

실행:

```bash
python scripts/evaluate_anti_spoofing.py
```

threshold 후보를 직접 넣고 싶으면:

```bash
python scripts/evaluate_anti_spoofing.py \
  --thresholds "0.03,0.05,0.07,0.10,0.20,0.50"
```

생성 결과:

```text
reports/anti_spoofing_results.csv
reports/anti_spoofing_threshold_metrics.csv
```

`anti_spoofing_results.csv`는 파일별 결과입니다.

```csv
file,label,spoof_score,configured_threshold,is_spoofed,correct,predicted_label
fake/fake_001.wav,fake,0.0785,0.07,true,true,real
real/real_001.wav,real,0.0211,0.07,false,true,real
```

`anti_spoofing_threshold_metrics.csv`는 threshold별 성능입니다.

```csv
threshold,total,correct,accuracy,tp,tn,fp,fn,precision,recall,false_positive_rate,false_negative_rate
0.07,20,16,0.8,8,8,2,2,0.8,0.8,0.2,0.2
```

여기서 중요한 값:

- `accuracy`: 전체 정확도
- `fp`: 실제 사람 음성을 fake로 잘못 잡은 수
- `fn`: fake 음성을 실제 사람 음성으로 놓친 수
- `false_positive_rate`: 정상 음성을 위험하다고 오판하는 비율
- `false_negative_rate`: fake를 놓치는 비율

IsFAM은 보이스피싱 방지 목적이므로 `fn`을 줄이는 것이 중요하지만, `fp`가 너무 높으면 정상 사용자 경험이 나빠집니다.

### Speaker Verification 평가 데이터 준비

화자 인증은 `pairs.csv`로 비교할 음성 쌍과 정답을 직접 지정합니다.

예시:

```text
datasets/speaker_verification/
  mother/
    enroll_001.wav
    test_001.wav
  father/
    enroll_001.wav
  unknown/
    unknown_001.wav
  pairs.csv
```

`pairs.csv` 형식:

```csv
audio_file_1,audio_file_2,label
mother/enroll_001.wav,mother/test_001.wav,same
mother/enroll_001.wav,father/enroll_001.wav,different
mother/enroll_001.wav,unknown/unknown_001.wav,different
```

`pairs.example.csv`를 복사해서 시작할 수 있습니다.

```bash
cp datasets/speaker_verification/pairs.example.csv datasets/speaker_verification/pairs.csv
```

실행:

```bash
python scripts/evaluate_speaker_verification.py
```

threshold 후보를 직접 넣고 싶으면:

```bash
python scripts/evaluate_speaker_verification.py \
  --thresholds "0.50,0.60,0.65,0.70,0.75,0.80"
```

생성 결과:

```text
reports/speaker_verification_results.csv
reports/speaker_verification_threshold_metrics.csv
```

`speaker_verification_results.csv`는 음성 쌍별 similarity를 저장합니다.

```csv
audio_file_1,audio_file_2,label,similarity,configured_threshold,is_same_speaker,correct
mother/enroll_001.wav,mother/test_001.wav,same,0.82,0.75,true,true
mother/enroll_001.wav,unknown/unknown_001.wav,different,0.12,0.75,false,true
```

`speaker_verification_threshold_metrics.csv`는 threshold별 성능입니다.

```csv
threshold,total,correct,accuracy,tp,tn,fp,fn,precision,recall,false_accept_rate,false_reject_rate
0.75,30,25,0.8333,12,13,2,3,0.8571,0.8,0.1333,0.2
```

화자 인증에서 중요한 값:

- `false_accept_rate`: 다른 사람을 가족으로 잘못 받아들이는 비율
- `false_reject_rate`: 진짜 가족을 가족이 아니라고 거절하는 비율
- `similarity`: SpeechBrain embedding cosine similarity

### 평가 결과로 설정 반영

평가 결과를 보고 threshold를 바꿀 때는 환경변수나 `.env`를 사용합니다.

```bash
ISFAM_SPEAKER_THRESHOLD=0.70 uvicorn app.main:app --reload
ISFAM_ANTI_SPOOFING_THRESHOLD=0.10 uvicorn app.main:app --reload
```

로컬 `.env` 예시:

```text
ISFAM_SPEAKER_THRESHOLD=0.70
ISFAM_ANTI_SPOOFING_THRESHOLD=0.10
```

주의: 현재 anti-spoofing 모델은 데모용 baseline입니다. 평가 CSV를 쌓은 뒤에도 성능이 부족하면 AASIST 계열 모델 추가, 모델 교체, ensemble, 청크 누적 판단 개선 순서로 고도화하는 것이 좋습니다.

## 예외 처리

서버는 다음 상황을 API 오류로 반환합니다.

- 파일 누락 또는 빈 파일: `400`
- 지원하지 않는 확장자: `415`
- 업로드 파일 크기 초과: `413`
- 음성 디코딩 실패: `422`
- 너무 짧은 음성: `400`
- embedding 추출, anti-spoofing 추론, 모델 로딩 오류: `500`

요청 처리 중 생성한 원본 임시 파일과 변환 wav 파일은 `finally` 블록에서 정리됩니다.

## 2차/3차/4차/4.5차 테스트 순서

1. 서버 실행:

```bash
cd /Users/leejooho/Desktop/FinNect
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2. 상태 확인:

```bash
curl http://127.0.0.1:8000/health
```

3. 가족 음성 등록:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/family/register" \
  -F "name=엄마" \
  -F "relation=mother" \
  -F "audio_file=@/Users/leejooho/Desktop/mother_voice.m4a"
```

4. 등록 목록 확인:

```bash
curl "http://127.0.0.1:8000/api/v1/family"
```

5. 특정 가족 확인:

```bash
curl "http://127.0.0.1:8000/api/v1/family/1"
```

6. 등록 삭제 테스트:

등록 가족 전체 비교를 먼저 테스트하려면 삭제는 마지막에 하세요.

7. 새 통화 음성을 등록 가족 전체와 비교:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/voice/verify-family" \
  -F "audio_file=@/Users/leejooho/Desktop/call_voice.m4a"
```

응답에서 확인할 값:

- `is_registered_family`: threshold 이상으로 매칭된 가족이 있는지
- `best_match`: 가장 비슷한 등록 가족
- `candidates`: 등록 가족별 similarity 목록
- `message`: `registered_family_matched` 또는 `no_registered_family_match`

8. 딥페이크 탐지만 단독 테스트:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anti-spoofing/detect" \
  -F "audio_file=@/Users/leejooho/Desktop/call_voice.m4a"
```

응답에서 확인할 값:

- `is_spoofed`: spoof/deepfake 의심 여부
- `spoof_score`: spoof label 확률 합산값
- `predicted_label`: 모델이 가장 높게 본 label
- `label_scores`: label별 확률
- `analyzed_segments`: 분석한 음성 구간 수
- `max_spoof_segment_index`: 가장 높은 spoof score가 나온 구간 번호

9. 가족 검증과 딥페이크 탐지를 함께 테스트:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/voice/verify-family-secure" \
  -F "audio_file=@/Users/leejooho/Desktop/call_voice.m4a"
```

응답에서 확인할 값:

- `is_trusted`: 등록 가족과 매칭되고 spoof가 아닌지
- `final_decision`: 최종 판단
- `family_verification`: 등록 가족 비교 결과
- `anti_spoofing`: 딥페이크 탐지 결과

10. 청크 기반 연속 분석 세션 테스트:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/voice-sessions/start"
```

응답의 `session_id`를 복사해서 아래 요청에 넣습니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/voice-sessions/{session_id}/chunks" \
  -F "chunk_index=0" \
  -F "audio_file=@/Users/leejooho/Desktop/chunk_0.m4a"
```

다음 청크는 `chunk_index=1`, `chunk_index=2`처럼 올리면 됩니다. `chunk_index`를 아예 빼면 서버가 자동으로 다음 번호를 붙입니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/voice-sessions/{session_id}/chunks" \
  -F "audio_file=@/Users/leejooho/Desktop/chunk_1.m4a"
```

중간 상태 조회:

```bash
curl "http://127.0.0.1:8000/api/v1/voice-sessions/{session_id}"
```

세션 종료:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/voice-sessions/{session_id}/end"
```

응답에서 확인할 값:

- `rolling_result.chunks_analyzed`: 지금까지 분석한 청크 수
- `rolling_result.total_chunks`: 업로드된 전체 청크 수
- `rolling_result.skipped_chunks`: 무음/저품질로 제외된 청크 수
- `rolling_result.max_spoof_score`: 지금까지 가장 높았던 spoof score
- `rolling_result.max_spoof_chunk_index`: spoof score가 가장 높았던 청크 번호
- `rolling_result.suspicious_chunks`: threshold를 넘은 suspicious 청크 수
- `rolling_result.best_family_match`: 지금까지 가장 비슷했던 등록 가족
- `rolling_result.family_match_chunks`: 같은 가족으로 반복 매칭된 청크 수
- `rolling_result.risk_level`: 현재 누적 위험도
- `quality`: 이번 청크의 길이, 음량, speech ratio
- `final_decision`: 이번 청크 하나만 놓고 본 판단

11. 등록 삭제 테스트:

```bash
curl -X DELETE "http://127.0.0.1:8000/api/v1/family/1"
```

12. Swagger 테스트:

```text
http://127.0.0.1:8000/docs
```

Swagger에서는 `family` 섹션의 `POST /api/v1/family/register`로 가족을 등록한 뒤, `voice` 섹션의 `POST /api/v1/voice/verify-family-secure`로 새 통화 음성을 업로드하면 됩니다. 청크 기반 테스트는 `voice-sessions` 섹션에서 `start -> chunks -> status -> end` 순서로 진행하면 됩니다. 딥페이크 탐지만 따로 확인하려면 `anti-spoofing` 섹션의 `POST /api/v1/anti-spoofing/detect`를 사용하면 됩니다.

## 확장 방향

현재는 speaker verification, 가족 voiceprint 저장, 등록 가족 전체 비교, Hugging Face audio classification 기반 anti-spoofing 탐지, 청크 기반 연속 분석 세션이 구현되어 있습니다. 이후 기능은 현재 구조에 맞춰 확장할 수 있습니다.

- 등록된 가족 voiceprint 저장: speaker embedding을 DB에 저장하고 재사용
- 가족 화이트리스트 비교: 여러 가족 embedding과 call embedding을 일괄 비교
- anti-spoofing 고도화: AASIST 같은 전용 모델로 교체하거나 ensemble 방식으로 확장
- Android 앱 연동: 앱에서 3~5초 음성 청크를 만들어 `voice-sessions` API로 반복 업로드

이 구조에서는 FastAPI 라우터가 모델 세부 구현을 직접 알지 않고 `SpeakerVerificationService`만 호출합니다. 따라서 anti-spoofing 모델을 추가할 때도 API 레이어에서 `SpeakerVerificationService`와 `AntiSpoofingService`를 조합하는 방식으로 확장할 수 있습니다.
