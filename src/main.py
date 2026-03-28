"""
KNU 학식 디스코드 알림 서비스 — 메인 실행 파일

전체 흐름:
1. 식당 설정 로드
2. 각 식당 페이지 크롤링
3. HTML 파싱 → 구조화된 데이터
4. 이전 데이터와 비교 (변경 감지)
5. 변경된 식당만 Discord 채널에 전송
6. 상태 파일 업데이트
"""

import json
import hashlib
import os
import sys
import logging
import time
from pathlib import Path

from src.scraper import fetch_menu_page
from src.parser import parse_weekly_menu
from src.formatter import format_header_message, format_weekly_embeds
from src.discord_sender import send_weekly_menu

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "restaurants.json"
STATE_PATH = BASE_DIR / "data" / "last_menus.json"


def load_config() -> list[dict]:
    """식당 설정을 로드합니다."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    """이전 전송 상태를 로드합니다."""
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    """전송 상태를 저장합니다."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def compute_content_hash(menu_dict: dict) -> str:
    """메뉴 데이터의 해시를 계산합니다."""
    content = json.dumps(menu_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def has_menu_changed(restaurant_id: str, menu_dict: dict, state: dict) -> bool:
    """
    식단이 변경되었는지 확인합니다.

    변경 기준:
    1. 이전에 전송한 기록이 없는 경우
    2. 내용의 해시가 다른 경우
    """
    old_state = state.get(restaurant_id, {})
    old_hash = old_state.get("content_hash", "")
    new_hash = compute_content_hash(menu_dict)

    if not old_hash:
        logger.info(f"[{restaurant_id}] 첫 번째 실행 — 전송 필요")
        return True

    if new_hash != old_hash:
        logger.info(f"[{restaurant_id}] 식단 변경 감지! (이전: {old_hash}, 현재: {new_hash})")
        return True

    logger.info(f"[{restaurant_id}] 변경 없음 — 스킵")
    return False


def main():
    """메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("KNU 학식 디스코드 알림 서비스 시작")
    logger.info("=" * 50)

    # 환경 변수에서 봇 토큰 읽기
    bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    # 설정 로드
    restaurants = load_config()
    state = load_state()
    updated = False

    logger.info(f"총 {len(restaurants)}개 식당 확인 예정")

    for restaurant in restaurants:
        name = restaurant["name"]
        shop_sqno = restaurant["shop_sqno"]
        channel_env = restaurant["channel_env"]
        emoji = restaurant["emoji"]
        restaurant_id = str(shop_sqno)

        logger.info(f"\n--- {emoji} {name} (shop_sqno={shop_sqno}) ---")

        # 채널 ID 확인
        channel_id = os.environ.get(channel_env)
        if not channel_id:
            logger.warning(f"[{name}] 채널 ID 환경 변수 '{channel_env}'가 설정되지 않았습니다. 스킵.")
            continue

        # 1. 크롤링
        html = fetch_menu_page(shop_sqno)
        if not html:
            logger.error(f"[{name}] 크롤링 실패. 스킵.")
            continue

        # 2. 파싱
        weekly_menu = parse_weekly_menu(html)
        if weekly_menu.is_empty():
            logger.info(f"[{name}] 식단 데이터 없음 (휴무 또는 미등록). 스킵.")
            continue

        menu_dict = weekly_menu.to_dict()

        # 3. 변경 감지
        if not has_menu_changed(restaurant_id, menu_dict, state):
            continue

        # 4. Discord Embed 포맷팅
        header = format_header_message(name, emoji, weekly_menu)
        embeds = format_weekly_embeds(name, weekly_menu)

        if not embeds:
            logger.warning(f"[{name}] Embed 생성 결과가 비어있습니다. 스킵.")
            continue

        logger.info(f"[{name}] {len(embeds)}개 Embed 생성, Discord에 전송 중...")

        # 5. Discord 전송
        success = send_weekly_menu(bot_token, channel_id, header, embeds)

        if success:
            # 6. 상태 업데이트
            state[restaurant_id] = {
                "name": name,
                "content_hash": compute_content_hash(menu_dict),
                "menu_data": menu_dict,
            }
            updated = True
            logger.info(f"[{name}] ✅ 전송 완료!")
        else:
            logger.error(f"[{name}] ❌ 전송 실패!")

        # Rate limit 방지를 위해 식당 간 1초 대기
        time.sleep(1)

    # 변경사항이 있으면 상태 파일 저장
    if updated:
        save_state(state)
        logger.info("\n상태 파일 업데이트 완료")
    else:
        logger.info("\n변경된 식단 없음 — 상태 파일 유지")

    logger.info("=" * 50)
    logger.info("실행 완료")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
