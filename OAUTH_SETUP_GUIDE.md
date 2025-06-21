# 🔐 고급 OAuth 설정 가이드

## 개요
고급 OAuth 설정은 Refresh Token을 포함하여 자동 갱신이 가능한 안정적인 인증 방법입니다.

## 🚀 설정 단계

### 1단계: Google Cloud Console 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. **프로젝트 선택** 또는 **새 프로젝트** 클릭
3. 프로젝트 이름 입력 (예: "YouTube News Analyzer")
4. **만들기** 클릭

### 2단계: YouTube Data API v3 활성화

1. 왼쪽 메뉴에서 **API 및 서비스** → **라이브러리** 클릭
2. 검색창에 "YouTube Data API v3" 입력
3. **YouTube Data API v3** 클릭
4. **사용** 버튼 클릭

### 3단계: OAuth 2.0 클라이언트 ID 생성

1. 왼쪽 메뉴에서 **API 및 서비스** → **사용자 인증 정보** 클릭
2. **사용자 인증 정보 만들기** → **OAuth 2.0 클라이언트 ID** 클릭
3. **동의 화면 구성** 필요 시:
   - **사용자 유형**: 외부 선택
   - **앱 이름**: "YouTube News Analyzer" 입력
   - **사용자 지원 이메일**: 본인 이메일 입력
   - **개발자 연락처 정보**: 본인 이메일 입력
   - **저장 후 계속** 클릭

4. **OAuth 2.0 클라이언트 ID** 생성:
   - **애플리케이션 유형**: 데스크톱 앱 선택
   - **이름**: "YouTube News Analyzer Desktop" 입력
   - **만들기** 클릭

### 4단계: credentials.json 파일 다운로드

1. 생성된 OAuth 2.0 클라이언트 ID 옆의 **다운로드** 버튼 클릭
2. 다운로드된 JSON 파일을 프로젝트 루트 디렉토리에 `credentials.json`으로 저장

### 5단계: 앱에서 사용

1. Streamlit 앱 실행
2. **구글 로그인 및 최신 동영상** 탭으로 이동
3. **⚙️ 고급 OAuth** 버튼 클릭
4. 브라우저가 열리면 구글 계정으로 로그인
5. 권한 허용 후 자동으로 설정 완료

## 🔧 파일 구조

```
Youtube_News/
├── app.py
├── auto_oauth_setup.py
├── credentials.json          # 여기에 저장
├── saved_google_credentials.json  # 자동 생성됨
└── ...
```

## ⚠️ 주의사항

### 보안
- `credentials.json` 파일은 절대 공개 저장소에 업로드하지 마세요
- `.gitignore`에 `credentials.json`과 `saved_google_credentials.json` 추가

### 권한
- YouTube Data API v3는 읽기 전용 권한만 요청합니다
- 개인 정보나 채널 관리 권한은 요청하지 않습니다

### 만료
- Access Token은 1시간 후 만료되지만 Refresh Token으로 자동 갱신됩니다
- Refresh Token은 장기간 유효합니다

## 🛠️ 문제 해결

### "OAuth 클라이언트 설정 파일이 없습니다" 오류
- `credentials.json` 파일이 프로젝트 루트에 있는지 확인
- 파일명이 정확한지 확인 (대소문자 구분)

### "API가 활성화되지 않았습니다" 오류
- YouTube Data API v3가 활성화되어 있는지 확인
- 프로젝트가 올바르게 선택되어 있는지 확인

### "권한이 거부되었습니다" 오류
- 동의 화면에서 필요한 권한을 허용했는지 확인
- 테스트 사용자로 등록되어 있는지 확인

### 포트 충돌 오류
- 8080 포트가 사용 중인 경우 다른 포트 사용
- `auto_oauth_setup.py`에서 포트 번호 변경

## 📞 지원

문제가 발생하면 다음을 확인해주세요:
1. Google Cloud Console에서 API 할당량 확인
2. OAuth 동의 화면 설정 확인
3. credentials.json 파일 형식 확인

## 🔄 자동 갱신

고급 OAuth 설정을 사용하면:
- Access Token이 만료되어도 자동으로 갱신됩니다
- 사용자가 다시 로그인할 필요가 없습니다
- 장기간 안정적으로 사용할 수 있습니다 