# 📮 우편번호 자동 입력 Web App

Google Sheets의 주소 데이터를 분석하여 우편번호를 자동으로 채워주는 Streamlit 앱입니다.

## 처리 흐름

```
주소 Column 읽기
    ↓
정규식 기반 주소 정제 (상세주소 제거)
    ↓
행안부 도로명주소 API 조회
    ↓
유사도 기반 최적 매칭
    ↓ (실패 시)
Gemini AI로 주소 보정 후 재조회
    ↓
우편번호 + 정확도(%) 시트에 기록
```

## 설치 및 실행

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. API 키 설정

`.streamlit/secrets.toml` 파일 생성:
```toml
GEMINI_API_KEY = "your-gemini-api-key"
JUSO_API_KEY = "your-juso-api-key"
```

- **Gemini API Key**: [Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급
- **도로명주소 API Key**: [도로명주소 개발자센터](https://business.juso.go.kr/addrlink/openApi/apiReqst.do)에서 발급

### 3. Google 서비스 계정 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 서비스 계정 생성
2. Google Sheets API, Google Drive API 활성화
3. JSON 키 파일을 `service_account.json`으로 프로젝트 루트에 저장
4. 대상 Google Sheet에 서비스 계정 이메일을 **편집자**로 공유

### 4. 실행
```bash
streamlit run app.py
```

## 파일 구조

| 파일 | 역할 |
|---|---|
| `app.py` | Streamlit 메인 UI |
| `config.py` | API 키 및 설정 |
| `zipcode_helper.py` | 우편번호 조회/추천 핵심 로직 |
| `gemini_helper.py` | Gemini AI 주소 정제 (fallback) |
| `sheets_handler.py` | Google Sheets 읽기/쓰기 |

## 정확도 기준

| 정확도 | 의미 |
|---|---|
| 90~100% | 정규식 정제 → API 직접 매칭 성공 |
| 70~85% | Gemini 보정 후 API 매칭 |
| 50% 이하 | 불확실한 매칭 (수동 확인 권장) |
| 0% / 빈칸 | 조회 실패 |
