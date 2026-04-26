"""
KNU 학식 디스코드 알림 서비스 — 일간 전송 봇 (스케줄러 버전)

전체 흐름:
1. 평일(월~금) 매일 오전 7시에 실행
2. 식당 설정 로드 및 크롤링
3. 주간 식단 중 "오늘 요일"에 해당하는 식단만 추출
4. Discord 채널에 전송
"""

import os
import sys
import logging
import time
from datetime import datetime
import pytz
import schedule
from pathlib import Path
from dotenv import load_dotenv

from src.scraper import fetch_menu_page
from src.parser import parse_weekly_menu
from src.formatter import format_daily_header_message, _format_day_embed
from src.discord_sender import send_daily_menu
import json

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "restaurants.json"

def load_config() -> list[dict]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def job():
    """매일 지정된 시간에 실행될 식단 전송 작업"""
    logger.info("=" * 50)
    logger.info("오늘의 식단 알림 전송 시작")
    
    # 한국 시간 기준으로 오늘 요일 구하기
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    weekday_idx = now.weekday()  # 0: 월, 1: 화, ..., 4: 금, 5: 토, 6: 일
    
    if weekday_idx > 4:
        logger.info("주말(토/일)이므로 식단 알림을 전송하지 않습니다.")
        return

    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    today_name = day_names[weekday_idx]
    
    logger.info(f"오늘은 {today_name}요일 입니다.")

    bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
        return

    restaurants = load_config()
    
    for restaurant in restaurants:
        name = restaurant["name"]
        shop_sqno = restaurant["shop_sqno"]
        channel_env = restaurant["channel_env"]
        emoji = restaurant["emoji"]

        logger.info(f"\n--- {emoji} {name} ---")

        channel_id = os.environ.get(channel_env)
        if not channel_id:
            logger.warning(f"[{name}] 채널 ID 누락. 스킵.")
            continue

        html = fetch_menu_page(shop_sqno)
        if not html:
            logger.error(f"[{name}] 크롤링 실패. 스킵.")
            continue

        weekly_menu = parse_weekly_menu(html)
        if weekly_menu.is_empty():
            logger.info(f"[{name}] 금주 식단 데이터가 없습니다.")
            continue

        # 오늘 요일에 해당하는 식단 찾기
        today_menu = None
        for day in weekly_menu.days:
            if day.day_name == today_name:
                today_menu = day
                break

        if not today_menu or not today_menu.meals:
            logger.info(f"[{name}] 오늘({today_name}요일) 식단이 없습니다. (휴무 등)")
            continue

        # Embed 포맷팅 (오늘 하루치만)
        header = format_daily_header_message(name, emoji, today_menu)
        embed = _format_day_embed(today_menu)

        if not embed:
            logger.warning(f"[{name}] Embed 생성 실패.")
            continue

        # 전송 (기존 함수 재사용하되 리스트에 1개만 넣음)
        success = send_daily_menu(bot_token, channel_id, header, [embed])

        if success:
            logger.info(f"[{name}] ✅ 전송 완료!")
        else:
            logger.error(f"[{name}] ❌ 전송 실패!")

        time.sleep(1)

    logger.info("오늘의 식단 전송 작업 완료")
    logger.info("=" * 50)

def main():
    logger.info("KNU 학식 일간 알림 봇 (스케줄러) 켜짐")
    
    # 1. 월~금 매일 아침 7시에 실행하도록 스케줄 등록 (명시적 KST 타임존 지정)
    KST = pytz.timezone('Asia/Seoul')
    schedule.every().monday.at("07:00", KST).do(job)
    schedule.every().tuesday.at("07:00", KST).do(job)
    schedule.every().wednesday.at("07:00", KST).do(job)
    schedule.every().thursday.at("07:00", KST).do(job)
    schedule.every().friday.at("07:00", KST).do(job)
    
    logger.info("⏰ 스케줄 등록 완료: 매주 평일 아침 7시")

    # (테스트용) 스크립트를 켤 때 일단 1번 즉시 실행해보고 싶다면 아래 주석을 푸세요
    # logger.info("초기 테스트 실행...")
    # job()

    # 무한 대기 루프
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1분마다 스케줄 확인

if __name__ == "__main__":
    main()
