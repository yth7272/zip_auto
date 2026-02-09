# ==========================================
# [설정값] API 키 및 기본 설정
# ==========================================
# ~/.secrets/ 에서 인증정보를 로드

import os


def load_env(filename: str) -> dict:
    """~/.secrets/ 에서 .env 파일을 읽어 dict로 반환"""
    path = os.path.expanduser(f"~/.secrets/{filename}")
    result = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            result[key.strip()] = value
    return result


# API Keys
_gemini = load_env("ai_gemini.env")
_juso = load_env("juso_api.env")

GEMINI_API_KEY = _gemini["GEMINI_API_KEY"]
JUSO_API_KEY = _juso["JUSO_API_KEY"]

# Google Sheets 서비스 계정
SERVICE_ACCOUNT_FILE = os.path.expanduser("~/.secrets/google_order_automation.json")
