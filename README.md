# YouTube 뉴스 자막 수집 및 요약 시스템

YouTube 동영상의 자막을 수집하고 저장하며, GPT-4o-mini를 활용하여 요약 및 분석하는 시스템입니다.

## 주요 기능

- YouTube 채널/키워드/URL을 등록하여 자동으로 자막 수집
- 스케줄링을 통한 정기적인 데이터 수집
- 청크 단위로 처리하여 길이 제한 없이 모든 자막 처리 가능
- GPT-4o-mini를 활용한 자막 요약 및 분석
- SQLite 데이터베이스에 메타데이터와 자막 저장

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

## 사용 방법

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

## 주의사항

- YouTube Data API 사용량 제한에 유의
- 여러 개의 API 키를 설정하여 할당량 초과 방지
- OpenAI API 사용 비용 발생에 주의 