# ==========================================
# [Gemini 헬퍼] AI 기반 주소 정제 (fallback)
# ==========================================
# 기존 정규식 정제 실패 시 Gemini로 주소를 보정합니다.

import json
import requests

from config import GEMINI_API_KEY

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.0-flash-lite:generateContent"

SYSTEM_PROMPT = """당신은 한국 주소 정제 전문가입니다. 
입력된 주소를 분석하여 행정안전부 도로명주소 API에서 검색 가능한 형태로 정제해주세요.

규칙:
1. 오타를 보정합니다 (예: 태헤란로 → 테헤란로)
2. 약어를 풀어씁니다 (예: 강남 → 서울특별시 강남구)
3. 지번 주소가 포함되면 도로명 주소 형태의 검색 키워드를 추출합니다
4. 상세주소(동/호/층)는 제거합니다
5. 검색에 불필요한 괄호 내용은 제거합니다

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요:
{"refined_address": "정제된 주소", "search_keyword": "API 검색용 키워드", "changes": "변경 사항 설명", "confidence": 0.0~1.0}

confidence 기준:
- 1.0: 명확한 주소, 변경 없음 또는 단순 정규화
- 0.8~0.9: 오타 보정, 약어 풀기 등 확실한 변환
- 0.5~0.7: 추정이 포함된 변환 (지번→도로명 등)
- 0.5 미만: 불확실한 변환
"""


def refine_address_with_gemini(address: str) -> dict:
    """
    Gemini API를 사용하여 주소를 정제합니다.

    Args:
        address: 원본 주소 문자열

    Returns:
        dict: {
            "refined_address": 정제된 주소,
            "search_keyword": API 검색용 키워드,
            "changes": 변경 사항,
            "confidence": 신뢰도 (0.0~1.0),
            "success": 성공 여부
        }
    """
    default_result = {
        "refined_address": address,
        "search_keyword": address,
        "changes": "정제 실패",
        "confidence": 0.0,
        "success": False,
    }

    if not address:
        return default_result

    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return default_result

    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_PROMPT},
                        {"text": f"주소를 정제해주세요: {address}"},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 256,
            },
        }

        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=15,
        )

        if response.status_code != 200:
            return default_result

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        # JSON 파싱 (마크다운 코드블록 제거)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)
        result["success"] = True
        return result

    except (json.JSONDecodeError, KeyError, IndexError, requests.RequestException):
        return default_result
