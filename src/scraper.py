"""
KNU 생활협동조합 식단 페이지 크롤러
"""

from __future__ import annotations
import requests
import time
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://coop.knu.ac.kr/sub03/sub01_01.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}


def fetch_menu_page(shop_sqno: int, max_retries: int = 3) -> str | None:
    """
    생협 사이트에서 해당 식당의 식단 HTML을 가져옵니다.

    Args:
        shop_sqno: 식당 고유번호 (예: 37 = 카페테리아 첨성)
        max_retries: 최대 재시도 횟수

    Returns:
        HTML 문자열 또는 실패 시 None
    """
    url = f"{BASE_URL}?shop_sqno={shop_sqno}"

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"
            logger.info(f"[{shop_sqno}] 페이지 가져오기 성공 (시도 {attempt}/{max_retries})")
            return response.text

        except requests.RequestException as e:
            logger.warning(f"[{shop_sqno}] 시도 {attempt}/{max_retries} 실패: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)  # 점진적 대기

    logger.error(f"[{shop_sqno}] 모든 재시도 실패")
    return None
