# ==========================================
# [우편번호 헬퍼] 우편번호 자동 추천 모듈
# ==========================================
# 원본 코드를 기반으로 Gemini fallback 통합

import re
import requests
from difflib import SequenceMatcher

from config import JUSO_API_KEY
from gemini_helper import refine_address_with_gemini


def search_zipcode_api(keyword, api_key=None):
    """행안부 도로명주소 API 조회"""
    if not keyword:
        return []

    if api_key is None:
        api_key = JUSO_API_KEY

    url = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
    params = {
        "confmKey": api_key,
        "currentPage": 1,
        "countPerPage": 10,
        "keyword": keyword,
        "resultType": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data["results"]["common"]["errorCode"] != "0":
                return []
            return data["results"]["juso"] or []
        return []
    except Exception:
        return []


def extract_base_address(full_address):
    """전체 주소에서 기본 주소(도로명/지번)만 추출 (상세주소 제거)"""
    if not full_address:
        return ""

    address = full_address.strip()

    # 괄호 안 내용 임시 보존
    paren_match = re.search(r"\([^)]+\)", address)
    paren_content = paren_match.group() if paren_match else ""

    address_no_paren = re.sub(r"\([^)]+\)", "", address).strip()

    base_address = None

    # 1단계: 도로명 주소 패턴 직접 추출 (~로/~길 + 건물번호)
    road_pattern = r"^(.+?(?:로|길)(?:\s*\d+번?길)?\s*\d+(?:-\d+)?)"
    road_match = re.match(road_pattern, address_no_paren)
    if road_match:
        base_address = road_match.group(1)

    # 2단계: 지번 주소 패턴 직접 추출 (동/리 + 번지)
    if not base_address:
        jibun_pattern = r"^(.+?(?:동\d*가?|리|읍|면)\s+\d+(?:-\d+)?)"
        jibun_match = re.match(jibun_pattern, address_no_paren)
        if jibun_match:
            base_address = jibun_match.group(1)

    # 3단계: 패턴 매칭 실패 시 상세주소 제거 후 반환
    if not base_address:
        detail_patterns = [
            r"\s+\d+동\s*\d*호?.*$",
            r"\s+[A-Za-z가-힣]+동(?![가-힣]|\d+가)\s*\d*호?.*$",
            r"\s+\d+층.*$",
            r"\s+\d+-\d+호?.*$",
            r"\s+\d+호.*$",
            r"\s+[가-힣]+아파트.*$",
            r"\s+[가-힣]+빌딩.*$",
            r"\s+[가-힣]+타워.*$",
            r"\s+[가-힣]+오피스텔.*$",
            r"\s+[가-힣]+빌라.*$",
            r"\s+[가-힣]+맨션.*$",
            r"\s+[가-힣]+주택.*$",
            r"\s+[가-힣]+마을.*$",
            r"\s+[가-힣]+단지.*$",
        ]
        base_address = address_no_paren
        for pattern in detail_patterns:
            base_address = re.sub(pattern, "", base_address, flags=re.IGNORECASE)

    if paren_content:
        base_address = f"{base_address} {paren_content}"

    return base_address.strip()


def calculate_similarity(str1, str2):
    """두 문자열의 유사도 (0.0~1.0)"""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def normalize_zipcode(zipcode):
    """우편번호 정규화 (4자리 → 5자리)"""
    if not zipcode:
        return ""
    zipcode_str = str(zipcode).strip()
    if len(zipcode_str) == 4 and zipcode_str.isdigit():
        return "0" + zipcode_str
    return zipcode_str


def _find_best_match(search_results, full_input, base_address):
    """검색 결과에서 가장 유사한 주소 찾기"""
    best_match = None
    best_similarity = 0.0

    for item in search_results:
        road_addr = item["roadAddr"]
        similarity = calculate_similarity(full_input, road_addr)

        # 키워드 매칭 보너스
        keywords = base_address.split()
        keyword_bonus = sum(0.1 for kw in keywords if kw in road_addr)
        similarity = min(1.0, similarity + keyword_bonus)

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = item

    return best_match, best_similarity


def recommend_zipcode(address: str, use_gemini_fallback: bool = True) -> dict:
    """
    주소를 기반으로 우편번호를 추천합니다.
    Gemini 활성화 시: Gemini 정제 → API 조회 → (실패 시) 정규식 fallback
    Gemini 비활성화 시: 정규식 정제 → API 조회

    Args:
        address: 주소 문자열
        use_gemini_fallback: Gemini AI 사용 여부

    Returns:
        dict: {
            zipcode, road_addr, accuracy, source,
            candidates, gemini_info
        }
    """
    result = {
        "zipcode": "",
        "road_addr": "",
        "accuracy": 0,
        "source": "none",
        "candidates": [],
        "gemini_info": None,
    }

    if not address:
        return result

    # ── 1단계: Gemini AI 정제 (활성화 시 우선 시도) ──
    if use_gemini_fallback:
        gemini_result = refine_address_with_gemini(address)
        result["gemini_info"] = gemini_result

        if gemini_result.get("success"):
            search_keyword = gemini_result.get("search_keyword", "")
            if search_keyword:
                search_results = search_zipcode_api(search_keyword)

                if not search_results:
                    refined = gemini_result.get("refined_address", "")
                    if refined and refined != search_keyword:
                        search_results = search_zipcode_api(refined)

                if search_results:
                    result["candidates"] = [
                        {"zipcode": item["zipNo"], "road_addr": item["roadAddr"]}
                        for item in search_results[:5]
                    ]

                    best_match, best_similarity = _find_best_match(
                        search_results, address, search_keyword
                    )

                    if best_match:
                        gemini_confidence = gemini_result.get("confidence", 0.5)
                        raw_accuracy = best_similarity * gemini_confidence
                        accuracy = min(95, max(30, int(raw_accuracy * 100)))

                        result["zipcode"] = best_match["zipNo"]
                        result["road_addr"] = best_match["roadAddr"]
                        result["accuracy"] = accuracy
                        result["source"] = "gemini+api"
                        return result

    # ── 2단계: 정규식 기반 정제 (Gemini 미사용 또는 실패 시) ──
    base_address = extract_base_address(address)
    if not base_address:
        base_address = address

    search_results = search_zipcode_api(base_address)

    if not search_results:
        shorter = re.sub(r"\s+\d+(-\d+)?$", "", base_address)
        if shorter != base_address:
            search_results = search_zipcode_api(shorter)

    if search_results:
        result["candidates"] = [
            {"zipcode": item["zipNo"], "road_addr": item["roadAddr"]}
            for item in search_results[:5]
        ]

        best_match, best_similarity = _find_best_match(
            search_results, address, base_address
        )

        if best_match:
            accuracy = min(100, int(best_similarity * 100))
            result["zipcode"] = best_match["zipNo"]
            result["road_addr"] = best_match["roadAddr"]
            result["accuracy"] = accuracy
            result["source"] = "regex+api"
            return result

    return result
