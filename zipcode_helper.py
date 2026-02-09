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

    # 상세주소 패턴 제거
    detail_patterns = [
        r"\s+\d+동\s*\d*호?.*$",
        r"\s+[A-Za-z가-힣]+동(?![가-힣])\s*\d*호?.*$",
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

    # 도로명 주소 기본 패턴 추출
    # ~로N번길, ~로N길 패턴 지원 (예: 재반로125번길 30)
    road_pattern = r"^(.+?(?:시|도|군|구)\s+.+?(?:로|길)(?:\s*\d+번?길)?\s*\d+(?:-\d+)?)"
    road_match = re.match(road_pattern, base_address)
    if road_match:
        base_address = road_match.group(1)

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
    기본 정규식 정제 → API 조회 → (실패 시) Gemini fallback

    Args:
        address: 주소 문자열
        use_gemini_fallback: Gemini fallback 사용 여부

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

    # ── 1단계: 정규식 기반 정제 ──
    base_address = extract_base_address(address)
    if not base_address:
        base_address = address

    # ── 2단계: API 조회 ──
    search_results = search_zipcode_api(base_address)

    # 결과 없으면 번호 제거 후 재시도
    if not search_results:
        shorter = re.sub(r"\s+\d+(-\d+)?$", "", base_address)
        if shorter != base_address:
            search_results = search_zipcode_api(shorter)

    # ── 3단계: 결과 있으면 매칭 ──
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

    # ── 4단계: Gemini fallback ──
    if use_gemini_fallback:
        gemini_result = refine_address_with_gemini(address)
        result["gemini_info"] = gemini_result

        if gemini_result.get("success"):
            search_keyword = gemini_result.get("search_keyword", "")
            if search_keyword:
                gemini_search_results = search_zipcode_api(search_keyword)

                if not gemini_search_results:
                    # refined_address로도 시도
                    refined = gemini_result.get("refined_address", "")
                    if refined and refined != search_keyword:
                        gemini_search_results = search_zipcode_api(refined)

                if gemini_search_results:
                    result["candidates"] = [
                        {"zipcode": item["zipNo"], "road_addr": item["roadAddr"]}
                        for item in gemini_search_results[:5]
                    ]

                    best_match, best_similarity = _find_best_match(
                        gemini_search_results, address, search_keyword
                    )

                    if best_match:
                        gemini_confidence = gemini_result.get("confidence", 0.5)
                        # Gemini 경유 정확도: API 유사도 × Gemini 신뢰도 기반
                        raw_accuracy = best_similarity * gemini_confidence
                        accuracy = min(85, max(30, int(raw_accuracy * 100)))

                        result["zipcode"] = best_match["zipNo"]
                        result["road_addr"] = best_match["roadAddr"]
                        result["accuracy"] = accuracy
                        result["source"] = "gemini+api"
                        return result

    return result
