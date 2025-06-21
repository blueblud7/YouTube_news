# YouTube 뉴스 자막 수집 및 요약 시스템

YouTube 동영상의 자막을 수집하고 저장하며, GPT-4o-mini를 활용하여 요약 및 분석하는 시스템입니다.

## 🔐 구글 로그인 시스템 가이드

### 개요
이 시스템은 YouTube Data API v3를 사용하여 구독 채널의 최신 동영상과 키워드 기반 검색을 제공합니다. 세 가지 로그인 방법을 지원합니다:

### 1. 🌐 Google OAuth Playground (간단)
**특징**: 빠르고 간단하지만 1시간 후 만료
**권장**: 테스트용 또는 임시 사용

#### 사용 방법:
1. [Google OAuth Playground](https://developers.google.com/oauthplayground/) 접속
2. 오른쪽 패널에서 `YouTube Data API v3` → `https://www.googleapis.com/auth/youtube.readonly` 선택
3. "Authorize APIs" 클릭 후 구글 계정으로 로그인
4. "Exchange authorization code for tokens" 클릭
5. 생성된 Access Token을 복사하여 앱에 입력

#### 주의사항:
- 토큰은 1시간 후 만료됩니다
- 만료 후 새로운 토큰을 발급받아야 합니다
- 자동 갱신이 불가능합니다

### 2. 🔑 Access Token 직접 입력
**특징**: 이미 가지고 있는 토큰 사용
**권장**: 기존 토큰이 있는 경우

#### 사용 방법:
1. 이미 발급받은 Access Token을 직접 입력
2. 토큰 유효성 검사 후 사용

#### 주의사항:
- 토큰 만료 시간을 확인해야 합니다
- 만료된 토큰은 사용할 수 없습니다

### 3. ⚙️ 고급 OAuth 설정 (권장)
**특징**: Refresh Token 포함, 자동 갱신 가능
**권장**: 장기간 사용하는 경우

#### 사전 설정:
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **API 및 서비스** → **라이브러리**에서 **YouTube Data API v3** 활성화
4. **사용자 인증 정보** → **사용자 인증 정보 만들기** → **OAuth 2.0 클라이언트 ID**
5. **애플리케이션 유형**: 데스크톱 앱 선택
6. **credentials.json** 파일 다운로드하여 프로젝트 루트에 저장

#### 사용 방법:
1. 앱에서 "고급 OAuth 설정" 선택
2. 브라우저가 열리면 구글 계정으로 로그인
3. 권한 허용 후 자동으로 설정 완료

#### 장점:
- Refresh Token이 포함되어 자동 갱신 가능
- 장기간 사용 가능
- 안정적인 인증

### 🔍 토큰 상태 확인
로그인 후 **로그인 상태** 탭에서 다음 정보를 확인할 수 있습니다:
- 토큰 유효성
- 만료 시간
- 자동 갱신 가능 여부
- 수동 갱신 버튼

### 💾 로그인 정보 저장
- 로그인 성공 시 자동으로 `saved_google_credentials.json` 파일에 저장
- 다음 실행 시 자동 로그인 시도
- 저장된 정보는 언제든지 삭제 가능

### 🚪 로그아웃
- **로그인 상태** 탭에서 로그아웃 버튼 클릭
- 세션 상태 초기화
- 저장된 정보는 유지 (선택적으로 삭제 가능)

## 주요 기능

- YouTube 채널/키워드/URL을 등록하여 자동으로 자막 수집
- 스케줄링을 통한 정기적인 데이터 수집
- 청크 단위로 처리하여 길이 제한 없이 모든 자막 처리 가능
- GPT-4o-mini를 활용한 자막 요약 및 분석
- SQLite 데이터베이스에 메타데이터와 자막 저장
- 🔐 구글 로그인을 통한 유튜브 구독 채널 및 키워드 기반 최신 동영상 검색

## 설치 방법

1. 레포지토리 클론 후 필요한 패키지 설치:

```bash
git clone <repository-url>
cd <repository-directory>
pip install -r requirements.txt
```

2. 환경 변수 설정:
   - `.env.local` 파일 생성
   - YouTube API 키와 OpenAI API 키 설정:

```
YOUTUBE_API_KEY_1=your_youtube_api_key_1
YOUTUBE_API_KEY_2=your_youtube_api_key_2
...
OPENAI_API_KEY=your_openai_api_key
```

3. 🔐 구글 OAuth 인증 설정 (새로운 기능):
   - [Google Cloud Console](https://console.cloud.google.com/)에서 새 프로젝트 생성
   - YouTube Data API v3 활성화
   - OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)
   - 다운로드한 JSON 파일을 `credentials.json`으로 이름 변경하여 프로젝트 루트에 저장

## 사용 방법

### 웹 인터페이스 실행

```bash
streamlit run app.py
```

### 구글 로그인 및 최신 동영상 기능

1. 🔐 구글 로그인: 사이드바에서 "구글 로그인 및 최신 동영상" 메뉴 선택
2. 📺 구독 채널 동영상: 로그인 후 구독 채널의 최신 동영상을 시간별로 필터링하여 확인
3. 🔍 키워드 검색: 특정 키워드로 최신 동영상을 검색하고 시간 범위 설정 가능
4. 🎬 원클릭 분석: 검색된 동영상을 바로 자막 분석 시스템으로 전송

⏰ 지원하는 시간 필터:
- 최신 (6시간 이내)
- 1일 이내
- 1주일 이내
- 1개월 이내

### 테스트 모드

기본 기능 테스트:

```bash
python main.py --test
```

### 채널 및 키워드 등록

모니터링할 채널 추가:

```bash
python main.py --add-channel "https://www.youtube.com/@channelname"
```

모니터링할 키워드 추가:

```bash
python main.py --add-keyword "검색어"
```

### 데이터 수집

등록된 채널과 키워드에서 데이터 즉시 수집:

```bash
python main.py --collect
```

### 스케줄러 설정 및 실행

스케줄러 실행 간격 설정(시간 단위):

```bash
python main.py --interval 12  # 12시간마다 실행
```

스케줄러 실행:

```bash
python main.py --schedule
```

## 프로젝트 구조

- `main.py`: 메인 실행 파일
- `youtube_handler.py`: YouTube API를 활용한 데이터 수집 기능
- `db_handler.py`: SQLite 데이터베이스 처리
- `llm_handler.py`: GPT-4o-mini를 활용한 요약 및 분석
- `config.py`: 환경 변수 및 설정 관리
- `check_transcripts.py`: 저장된 자막 정보 확인 도구
- 🔐 `google_auth_handler.py`: 구글 OAuth 인증 및 유튜브 API 연동
- 🎬 `app.py`: Streamlit 웹 인터페이스 (새로운 기능 포함)

## 자막 처리 특징

- 모든 길이의 자막을 청크 단위로 나누어 처리
- 각 청크별 요약/분석 후 최종 통합 결과 생성
- 한국어 자막 우선, 없는 경우 영어 자막 사용
- 자동 생성 자막과 수동 생성 자막 모두 지원

## 지원하는 URL 형식

- 채널 URL: `https://www.youtube.com/@channelname`
- 비디오 URL: `https://www.youtube.com/watch?v=VIDEO_ID`
- 단축 URL: `https://youtu.be/VIDEO_ID`
- 쇼츠 URL: `https://www.youtube.com/shorts/VIDEO_ID`
- 임베드 URL: `https://www.youtube.com/embed/VIDEO_ID`

## 새로운 기능: 구글 로그인 및 최신 동영상

### 주요 특징
- 🔐 구글 OAuth 인증: 안전한 구글 계정 로그인
- 📺 구독 채널 동영상: 구독 중인 채널의 최신 동영상 자동 수집
- 🔍 키워드 검색: 특정 키워드로 최신 동영상 검색
- ⏰ 시간 필터링: 최신, 1일, 1주일, 1개월 단위로 필터링
- 🎬 원클릭 분석: 검색된 동영상을 바로 자막 분석 시스템으로 전송

### 사용 시나리오
1. 📰 뉴스 모니터링: 특정 키워드로 최신 뉴스 동영상 검색
2. 📅 구독 채널 관리: 구독 채널의 최신 콘텐츠 확인
3. 🌟 트렌드 분석: 특정 주제의 최신 동영상 트렌드 파악
4. 📚 콘텐츠 큐레이션: 관심 있는 동영상을 자동으로 수집하고 분석

## 주의사항

- YouTube Data API 사용량 제한에 유의
- 여러 개의 API 키를 설정하여 할당량 초과 방지
- OpenAI API 사용 비용 발생에 주의
- 🔐 구글 OAuth 인증 시 credentials.json 파일 보안에 주의 