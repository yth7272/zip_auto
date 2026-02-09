# ==========================================
# [설정값] API 키 및 기본 설정
# ==========================================
# 로컬: ~/.secrets/ 에서 로드
# Streamlit Cloud: st.secrets 에서 로드

import os

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


def _get_key(env_file: str, key: str) -> str:
    """로컬 ~/.secrets/ 우선, 없으면 st.secrets fallback"""
    path = os.path.expanduser(f"~/.secrets/{env_file}")
    if os.path.exists(path):
        return load_env(env_file)[key]
    return st.secrets[key]


# API Keys
GEMINI_API_KEY = _get_key("ai_gemini.env", "GEMINI_API_KEY")
JUSO_API_KEY = _get_key("juso_api.env", "JUSO_API_KEY")

# Google Sheets 서비스 계정
_local_sa = os.path.expanduser("~/.secrets/google_order_automation.json")
if os.path.exists(_local_sa):
    SERVICE_ACCOUNT_FILE = _local_sa
    SERVICE_ACCOUNT_INFO = None
else:
    SERVICE_ACCOUNT_FILE = None
    SERVICE_ACCOUNT_INFO = dict(st.secrets["gcp_service_account"])
