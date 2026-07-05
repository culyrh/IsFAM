# IsFAM Mobile Demo

Capacitor 기반 Android 시연용 모바일 앱입니다. AI 모델은 앱 안에서 돌리지 않고, 기존 FastAPI 서버를 호출합니다.

## 실행 전 준비

백엔드 서버를 먼저 실행합니다.

```bash
cd /Users/leejooho/Desktop/FinNect
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Android 에뮬레이터에서는 앱의 기본 API 주소가 아래 값으로 설정되어 있습니다.

```text
http://10.0.2.2:8000
```

실제 안드로이드 기기에서 테스트할 때는 앱 홈 화면의 API 서버 주소를 Mac의 같은 Wi-Fi IP로 바꿉니다.

```text
http://192.168.x.x:8000
```

## 설치

```bash
cd /Users/leejooho/Desktop/FinNect/mobile
npm install
```

## 웹으로 먼저 확인

```bash
npm run dev
```

브라우저:

```text
http://127.0.0.1:5173
```

## Android 프로젝트 생성

처음 한 번만 실행합니다.

```bash
npm run build
npm run cap:add:android
npm run cap:sync
npm run android
```

Android Studio가 열리면 에뮬레이터 또는 기기에 설치해서 시연합니다.

## 시연 흐름

1. `가족` 탭에서 가족 목소리를 등록합니다.
2. `검사` 탭에서 음성 파일 하나를 바로 분석합니다.
3. `통화` 탭에서 실제 음성 파일과 AI 음성 파일을 넣습니다.
4. `랜덤 통화 시작`을 누르면 둘 중 하나가 재생됩니다.
5. 약 10초 뒤 실제 음성인지 AI 음성인지 선택합니다.
6. 앱이 FastAPI 서버로 파일을 보내고 IsFAM AI 결과를 보여줍니다.

## 현재 범위

- 딥보이스 생성 기능은 없습니다.
- 사용자가 넣은 실제/AI 음성 파일을 이용해 실제 사용처럼 보이는 시뮬레이션만 합니다.
- Android 통화 오디오 직접 캡처는 아직 구현하지 않았습니다.
