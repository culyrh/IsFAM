# IsFAM

IsFAM은 가족 사칭형 AI 보이스피싱을 줄이기 위한 음성 기반 가족 확인 시스템입니다.

핵심 목표는 "이 음성이 딥보이스인가?" 하나만 맞히는 것이 아니라, 전화 중 들리는 목소리를 **등록된 가족으로 신뢰해도 되는지**를 판단하는 것입니다. 이를 위해 IsFAM은 가족 화자 인증, 딥보이스 탐지, 통화 구간별 누적 판단을 결합한 하이브리드 AI 위험도 알고리즘을 사용합니다.

## 개발 요약

IsFAM에서 실제로 개발한 핵심 기능은 다음과 같습니다.

```text
1. 가족 음성 등록
   가족의 실제 음성을 AI speaker embedding으로 변환하고 DB에 voiceprint로 저장합니다.

2. 다중 voiceprint 기반 가족 프로필
   가족 1명당 여러 음성 샘플을 등록하고, 같은 name/relation을 하나의 가족 프로필로 묶습니다.

3. 통화 음성 유사도 계산
   새 통화 음성을 embedding으로 변환한 뒤, 등록 가족 voiceprint와 cosine similarity를 계산합니다.

4. median similarity 기반 안정화
   최고점 하나에 의존하지 않고 max/mean/median similarity를 함께 계산해 튀는 점수의 영향을 줄입니다.

5. 가족 불일치 우선 탐지
   등록 가족과 충분히 비슷하지 않으면 AI 여부와 관계없이 가족 사칭 위험으로 판단합니다.

6. anti-spoofing 보조 판단
   딥보이스 탐지 모델의 spoof_score를 보조 신호로 사용해 위험도를 강화합니다.

7. 설명 가능한 위험도 출력
   safe/caution/danger, risk_score, final_decision, decision_reasons를 API 응답으로 제공합니다.

8. 객관 평가 리포트
   현재 등록 가족 음성으로 같은 화자/다른 화자 pair를 만들고 threshold별 정확도, FAR, FRR을 산출합니다.
```

현재 구현된 판단 흐름은 다음과 같습니다.

```text
가족 등록 음성
  -> speaker embedding 추출
  -> SQLite DB에 voiceprint 저장

새 통화 음성
  -> speaker embedding 추출
  -> 등록 가족 voiceprint와 similarity 계산
  -> anti-spoofing spoof_score 계산
  -> IsFAM Risk Scoring
  -> safe / caution / danger
```

## 문제 정의

최근 보이스피싱은 단순히 낯선 번호로 돈을 요구하는 수준을 넘어, 가족의 목소리를 AI로 흉내 내는 방식으로 발전하고 있습니다. 사용자는 짧은 통화 안에서 상대가 진짜 가족인지, AI로 변조된 목소리인지 판단해야 합니다.

IsFAM은 다음 상황을 판별합니다.

```text
가족 실제 음성          -> 안전
가족이 아닌 실제 음성   -> 확인 필요 또는 위험
가족을 흉내 낸 AI 음성  -> 위험
일반 AI/TTS 음성        -> 위험
잡음이 심한 통화 음성   -> 확인 필요
```

## AI 구조

IsFAM은 단일 모델에 의존하지 않습니다. 현재 대회 시연 버전은 별도 가짜 가족 음성 데이터가 없어도 동작하도록 **가족 voiceprint 불일치 탐지**를 1차 기준으로 사용합니다.

```text
전화 음성
  -> 음성 전처리
  -> 가족 voiceprint 비교
  -> 딥보이스 탐지
  -> 가족 중심 IsFAM Risk Scoring
  -> 안전 / 확인 필요 / 위험
```

### 1. 가족 화자 인증

등록된 가족 음성을 speaker embedding으로 변환해 SQLite DB에 저장합니다. 전화 중 들어온 음성도 같은 방식으로 embedding을 추출한 뒤, 등록된 가족 voiceprint와 cosine similarity를 계산합니다.

사용 모델:

```text
speechbrain/spkrec-ecapa-voxceleb
```

### 2. 딥보이스 탐지

전화 음성을 일정 길이의 구간으로 나누고, 각 구간에 대해 real/spoof 분류 모델을 실행합니다.

사용 모델:

```text
Vansh180/deepfake-audio-wav2vec2
```

### 3. IsFAM Risk Scoring

기존 오픈소스 모델의 출력값을 그대로 사용하지 않고, 팀만의 위험도 알고리즘으로 최종 판단을 만듭니다. 이때 가장 중요한 신호는 "등록된 가족 목소리와 충분히 비슷한가"입니다. 실제 보이스피싱에서는 AI 음성이 아니더라도 가족이 아닌 사람이 가족처럼 말하면 위험하기 때문입니다.

판단에 사용하는 신호는 다음과 같습니다.

```text
가족 voiceprint 유사도
등록 가족 기준 미달 여부
AI 합성 음성 의심 점수
등록 샘플 수
등록 샘플 간 점수 안정성
통화 chunk별 반복 경고 여부
```

최종 출력은 다음 3단계입니다.

```text
safe     안전
caution  확인 필요
danger   위험
```

## 독창적 최적화

대회 기준에서 중요한 부분은 단순히 오픈소스 모델을 호출하는 것이 아니라, 서비스 문제에 맞게 AI 출력을 재해석하고 안정화하는 것입니다. IsFAM은 다음 최적화를 적용했습니다.

### 다중 voiceprint 집계

가족 1명당 음성 샘플을 여러 개 등록할 수 있습니다. 같은 `name`과 `relation`으로 등록된 voiceprint는 하나의 가족 프로필로 묶입니다.

단일 최고점만 사용하면 우연히 점수가 높게 나온 샘플 때문에 오판할 수 있으므로, IsFAM은 다음 값을 함께 계산합니다.

```text
sample_count
max_similarity
mean_similarity
median_similarity
```

최종 가족 매칭 점수는 안정성을 위해 median similarity를 중심으로 판단합니다.

### 가족 중심 위험도 정책

현재 IsFAM은 다음 기준으로 1차 탐지를 강화합니다.

```text
등록 가족 similarity >= 기준값
-> 안전 후보

등록 가족 similarity가 기준값에 근접
-> 확인 필요

등록 가족 similarity가 기준값보다 크게 낮음
-> AI 여부와 무관하게 위험
```

딥보이스 탐지 모델은 이 판단을 보조합니다.

```text
가족 아님 + AI 음성 의심 낮음
-> 등록 가족과 다른 목소리로 위험 또는 확인 필요

가족 아님 + AI 음성 의심 높음
-> 가족 사칭형 AI 음성 가능성으로 고위험

가족과 비슷함 + AI 음성 의심 높음
-> 가족 목소리 흉내 가능성으로 확인 필요 또는 위험
```

### 설명 가능한 위험도

`/api/v1/voice/verify-family-secure` 응답은 단순 boolean만 반환하지 않습니다.

```json
{
  "is_trusted": false,
  "risk_level": "danger",
  "risk_score": 0.82,
  "final_decision": "spoofed_family_like_voice",
  "decision_reasons": [
    "가장 가까운 가족 voiceprint 유사도 0.6410가 기준에 근접하지만 통과하지 못했습니다.",
    "AI 합성 음성 의심 점수 0.4200가 강한 경고 기준에 도달했습니다."
  ]
}
```

이 구조는 심사위원과 사용자에게 AI가 왜 그런 판단을 했는지 설명할 수 있게 합니다.

### 통화 구간 누적 분석

실제 통화는 한 번의 음성 파일보다 불안정합니다. IsFAM은 voice session API를 통해 3~5초 단위 chunk를 누적 분석할 수 있습니다.

누적 판단에는 다음 정보가 사용됩니다.

```text
분석 가능한 chunk 수
저품질로 제외된 chunk 수
가족으로 확인된 chunk 수
spoof 의심 chunk 수
최대 spoof score
동일 가족이 반복 확인됐는지 여부
```

이를 통해 짧은 구간 하나의 실수보다 전체 통화 흐름을 기준으로 판단합니다.

## 평가 기준 대응

### AI 모델/알고리즘 적절성

IsFAM은 문제를 두 개의 AI 세부 문제로 분해합니다.

```text
가족인지 확인        -> Speaker Verification
AI 합성 음성인지 확인 -> Anti-Spoofing
최종 서비스 판단      -> IsFAM Risk Scoring
```

가족 사칭 보이스피싱은 "딥보이스 여부"만으로는 해결되지 않습니다. 진짜 사람 목소리라도 가족이 아니면 위험할 수 있기 때문에, 가족 인증과 딥보이스 탐지를 함께 사용합니다.

### 기존 오픈소스 활용을 넘는 최적화

적용된 팀 최적화는 다음과 같습니다.

```text
다중 가족 voiceprint 집계
median similarity 기반 가족 판단
등록 가족 불일치 우선 탐지
AI 합성 점수의 보조 위험도 반영
등록 샘플 수에 따른 신뢰도 조정
chunk 기반 누적 위험 판단
판단 근거 문장 생성
```

### 입력값에 대한 안정적 출력

결과는 단순히 `true/false`가 아니라 다음처럼 안정적인 상태로 제공됩니다.

```text
safe     가족으로 신뢰 가능
caution  가족 확인 필요
danger   보이스피싱 또는 AI 사칭 의심
```

애매한 입력은 억지로 안전 처리하지 않고 `caution`으로 분리합니다.

### 기술 지표

대회 시연 및 평가 데이터에서 다음 지표를 측정할 수 있습니다.

```text
가족/비가족 판별 정확도
AI 합성 음성 탐지 정확도
위험 통화 탐지율
정상 가족 통화 오탐률
평균 처리 시간
chunk 1개당 분석 시간
```

권장 목표:

```text
가족/비가족 판별 정확도 85% 이상
위험 통화 탐지율 90% 이상
chunk 분석 시간 2초 이하
```

현재 등록 가족 음성 10개 기준으로 speaker verification 분리 성능을 측정했습니다.

```text
파일 수: 10개
화자 수: 2명(mom, daughter)
같은 화자 pair: 20개
다른 화자 pair: 25개
같은 화자 평균 유사도: 0.7898
같은 화자 최소 유사도: 0.6676
다른 화자 평균 유사도: 0.4311
다른 화자 최대 유사도: 0.5021
분리 여유도(min same - max different): 0.1655
threshold 0.65 기준 pair accuracy: 100%
threshold 0.65 기준 false accept rate: 0%
threshold 0.65 기준 false reject rate: 0%
leave-one-out 화자 식별 정확도: 100% (10/10)
```

현재 데이터에서는 `ISFAM_SPEAKER_THRESHOLD=0.65`가 가장 안정적입니다. 단, 이 지표는 등록 가족 음성 내부 분리 성능입니다. 가짜 가족 음성이나 실제 비가족 음성이 없기 때문에 딥보이스 탐지 정확도와 외부 비가족 탐지 정확도는 별도 데이터 확보 전까지 정량화할 수 없습니다.

#### 지표 읽는 법

유사도는 높을수록 등록 가족 목소리와 비슷하다는 의미입니다.

```text
similarity 높음 -> 같은 사람일 가능성이 높음
similarity 낮음 -> 다른 사람일 가능성이 높음
```

현재 데이터에서 중요한 값은 다음 두 개입니다.

```text
같은 화자 최소 유사도: 0.6676
다른 화자 최대 유사도: 0.5021
```

같은 사람끼리 비교한 최저점이 `0.6676`이고, 다른 사람끼리 비교한 최고점이 `0.5021`입니다. 따라서 기준값을 `0.65`로 잡으면 현재 데이터에서는 같은 사람은 통과하고 다른 사람은 거절됩니다.

```text
0.65 이상 -> 등록 가족으로 판단
0.65 미만 -> 등록 가족과 다른 목소리로 판단
```

`분리 여유도 0.1655`는 두 분포 사이의 빈 공간입니다.

```text
0.6676 - 0.5021 = 0.1655
```

이 값이 클수록 같은 가족 목소리와 다른 목소리가 더 잘 분리됩니다.

### 데이터 수집/처리 타당성

모델을 새로 학습하지 않더라도 평가 데이터는 필요합니다. IsFAM은 다음 데이터셋 구조를 기준으로 threshold와 위험도 점수를 검증합니다.

```text
datasets/eval/
  family_real/        등록 가족의 실제 음성
  non_family_real/    가족이 아닌 사람의 실제 음성
  family_deepvoice/   가족 목소리를 AI로 흉내 낸 음성
  ai_voice/           일반 TTS 또는 AI 음성
  noisy_call/         잡음이 포함된 통화 음성
```

이 데이터는 모델 학습용이 아니라, 서비스 판단 기준 검증과 성능 측정용입니다.

## 주요 API

### 가족 음성 등록

```bash
curl -X POST http://127.0.0.1:8000/api/v1/family/register \
  -F "name=엄마" \
  -F "relation=mother" \
  -F "audio_file=@samples/mother_01.wav"
```

같은 가족을 여러 번 등록할 때는 같은 `name`, `relation`을 사용합니다.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/family/register \
  -F "name=엄마" \
  -F "relation=mother" \
  -F "audio_file=@samples/mother_02.wav"
```

### 가족 여부 확인

```bash
curl -X POST http://127.0.0.1:8000/api/v1/voice/verify-family \
  -F "audio_file=@samples/call.wav"
```

### 가족 여부 + 딥보이스 통합 판단

```bash
curl -X POST http://127.0.0.1:8000/api/v1/voice/verify-family-secure \
  -F "audio_file=@samples/call.wav"
```

응답 예시:

```json
{
  "is_trusted": true,
  "risk_level": "safe",
  "risk_score": 0.04,
  "final_decision": "trusted_family_voice",
  "decision_reasons": [
    "엄마 voiceprint와 유사도 0.8123로 기준보다 0.0623 높습니다.",
    "AI 합성 음성 의심 점수 0.0100가 기준보다 낮습니다.",
    "3개 등록 샘플 기준 유사도 편차가 안정적입니다."
  ]
}
```

### 통화 세션 시작

```bash
curl -X POST http://127.0.0.1:8000/api/v1/voice-sessions/start
```

### 통화 chunk 분석

```bash
curl -X POST http://127.0.0.1:8000/api/v1/voice-sessions/{session_id}/chunks \
  -F "audio_file=@samples/chunk_01.wav"
```

### 통화 세션 상태 확인

```bash
curl http://127.0.0.1:8000/api/v1/voice-sessions/{session_id}
```

## 실행 방법

### 1. Python 환경 준비

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. FastAPI 서버 실행

```bash
uvicorn app.main:app --reload
```

서버 주소:

```text
http://127.0.0.1:8000
```

Swagger 문서:

```text
http://127.0.0.1:8000/docs
```

### 3. 모바일 데모 실행

```bash
cd mobile
npm install
npm run dev
```

모바일 데모 주소:

```text
http://127.0.0.1:5173
```

## 환경변수

설정은 `app/core/config.py`에 있으며 `ISFAM_` prefix로 덮어쓸 수 있습니다.

```bash
ISFAM_SPEAKER_THRESHOLD=0.65 uvicorn app.main:app --reload
ISFAM_ANTI_SPOOFING_THRESHOLD=0.50 uvicorn app.main:app --reload
ISFAM_VOICE_SESSION_STRONG_SPOOF_SCORE=0.80 uvicorn app.main:app --reload
ISFAM_DEVICE=cpu uvicorn app.main:app --reload
```

주요 설정:

```text
ISFAM_SPEAKER_THRESHOLD
가족 voiceprint 유사도 기준

ISFAM_ANTI_SPOOFING_THRESHOLD
AI 합성 음성 탐지 기준

ISFAM_VOICE_SESSION_STRONG_SPOOF_SCORE
즉시 위험으로 볼 강한 spoof 기준

ISFAM_DATABASE_PATH
SQLite DB 경로, 기본값 data/isfam.sqlite3

ISFAM_DEVICE
cpu, cuda, auto 중 선택
```

## 프로젝트 구조

```text
app/
  api/routes/
    family.py              가족 등록 API
    voice.py               음성 비교 및 보안 검증 API
    voice_session.py       통화 chunk 누적 분석 API
    anti_spoofing.py       딥보이스 단독 탐지 API
  services/
    speaker_service.py     speaker embedding 추출 및 비교
    voiceprint_service.py  가족 voiceprint 등록/집계/검증
    anti_spoofing_service.py
    risk_scoring_service.py
  repositories/
    family_repository.py
    voice_session_repository.py
  db/
    session.py
mobile/
  src/
    main.js                모바일 통화 데모 로직
datasets/
  README.md
demo_samples/
  README.md
```

## 시연 시나리오

1. 가족 음성을 3개 이상 등록합니다.
2. 실제 가족 통화 음성을 업로드합니다.
3. 가족이 아닌 사람의 음성을 업로드합니다.
4. AI로 만든 가족 유사 음성을 업로드합니다.
5. 결과가 `safe`, `caution`, `danger`로 나뉘는지 확인합니다.
6. 응답의 `decision_reasons`로 판단 근거를 설명합니다.

평가 폴더의 등록 음성을 DB에 자동 등록:

```bash
.venv/bin/python scripts/register_eval_family.py
```

평가 폴더의 테스트 음성을 CSV로 분석:

```bash
.venv/bin/python scripts/evaluate_isfam_eval.py
```

현재 등록 가족 음성의 객관 지표 생성:

```bash
.venv/bin/python scripts/evaluate_family_voiceprints.py
```

## 현재 한계와 개선 계획

현재 버전은 오픈소스 사전학습 모델을 기반으로 하며, 별도 모델 학습은 수행하지 않습니다. 따라서 특정 한국어 통화 환경, 낮은 품질의 녹음, 최신 딥보이스 생성 모델에는 성능 편차가 생길 수 있습니다.

개선 계획:

```text
평가 데이터셋 구축
threshold 자동 튜닝 스크립트 추가
한국어 통화 데이터 기반 모델 비교
등록 문장 기반 active challenge 추가
위험도 점수 리포트 자동 생성
```

## 발표용 요약

IsFAM은 단일 AI 모델의 결과에 의존하지 않고, 가족 화자 인증 모델과 딥보이스 탐지 모델의 출력을 통화 구간별로 누적 분석하여 가족 사칭 위험도를 산출하는 하이브리드 AI 판별 시스템입니다. 다중 voiceprint 집계, median similarity 기반 안정화, AI 합성 점수의 보조 위험도 반영, 설명 가능한 decision reason을 통해 기존 오픈소스 활용을 넘어 서비스 도메인에 맞춘 독자적 최적화를 적용했습니다.
