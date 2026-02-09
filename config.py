# ==========================================
# [설정값] API 키 및 기본 설정
# ==========================================
# 로컬: ~/.secrets/ 에서 로드
# Streamlit Cloud: st.secrets 에서 로드

import os
import sys

import streamlit as st


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


def _is_local() -> bool:
    """로컬 환경 여부 (~/.secrets/ 디렉토리 존재 확인)"""
    return os.path.isdir(os.path.expanduser("~/.secrets"))


IS_LOCAL = _is_local()

if IS_LOCAL:
    # ── 로컬: ~/.secrets/ 파일에서 로드 ──
    _gemini = load_env("ai_gemini.env")
    _juso = load_env("juso_api.env")
    GEMINI_API_KEY = _gemini["GEMINI_API_KEY"]
    JUSO_API_KEY = _juso["JUSO_API_KEY"]

    SERVICE_ACCOUNT_FILE = os.path.expanduser("~/.secrets/google_order_automation.json")
    SERVICE_ACCOUNT_INFO = None
else:
    # ── Streamlit Cloud: st.secrets 에서 로드 ──
    try:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
        JUSO_API_KEY = st.secrets["JUSO_API_KEY"]
        SERVICE_ACCOUNT_FILE = None
        SERVICE_ACCOUNT_INFO = dict(st.secrets["gcp_service_account"])
    except KeyError as e:
        available = list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else []
        st.error(
            f"Secrets 설정 오류: `{e}` 키를 찾을 수 없습니다.\n\n"
            f"현재 등록된 키: `{available}`\n\n"
            "Streamlit Cloud > Settings > Secrets 에 "
            "GEMINI_API_KEY, JUSO_API_KEY, [gcp_service_account] 를 설정하세요."
        )
        sys.exit(1)
