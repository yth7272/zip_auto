#!/usr/bin/env python3
"""
Streamlit Cloud용 secrets.toml 생성 스크립트

~/.secrets/ 의 로컬 시크릿 파일들을 읽어
Streamlit Cloud > Settings > Secrets 에 붙여넣을 TOML 텍스트를 생성한다.

핵심: private_key를 싱글라인 문자열 + \n 이스케이프로 변환
      (triple-quoted 멀티라인은 Streamlit Cloud TOML 파서에서 깨질 수 있음)
"""

import json
import os
import sys


def load_env(filepath: str) -> dict:
    result = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            result[key.strip()] = value
    return result


def main():
    secrets_dir = os.path.expanduser("~/.secrets")

    # 1) API 키 로드
    gemini = load_env(os.path.join(secrets_dir, "ai_gemini.env"))
    juso = load_env(os.path.join(secrets_dir, "juso_api.env"))

    # 2) GCP 서비스 계정 JSON 로드
    sa_path = os.path.join(secrets_dir, "google_order_automation.json")
    with open(sa_path) as f:
        sa = json.load(f)

    # 3) TOML 생성
    lines = []
    lines.append("# Streamlit Cloud Secrets")
    lines.append(f'GEMINI_API_KEY = "{gemini["GEMINI_API_KEY"]}"')
    lines.append(f'JUSO_API_KEY = "{juso["JUSO_API_KEY"]}"')
    lines.append("")
    lines.append("[gcp_service_account]")

    for key, value in sa.items():
        # private_key: 반드시 싱글라인 이스케이프 문자열로 출력
        # 나머지: 일반 문자열
        if isinstance(value, str):
            # \n을 리터럴 \\n으로 이스케이프 (TOML 싱글라인 문자열)
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            lines.append(f'{key} = "{escaped}"')
        else:
            lines.append(f"{key} = {json.dumps(value)}")

    toml_text = "\n".join(lines) + "\n"

    # 4) 출력
    print("=" * 60)
    print("아래 내용을 Streamlit Cloud > Settings > Secrets 에 붙여넣으세요")
    print("=" * 60)
    print()
    print(toml_text)

    # 5) 파일로도 저장 (참고용)
    out_path = os.path.join(os.path.dirname(__file__), ".streamlit_secrets_toml")
    with open(out_path, "w") as f:
        f.write(toml_text)
    os.chmod(out_path, 0o600)
    print(f"[저장됨] {out_path}")


if __name__ == "__main__":
    main()
