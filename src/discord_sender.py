"""
Discord Bot REST API를 사용하여 메시지를 전송합니다.
Webhook이 아닌 Bot 토큰 방식으로, 1개 토큰으로 여러 채널에 전송 가능합니다.
"""

from __future__ import annotations
import requests
import logging
import time

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


def send_message(
    bot_token: str,
    channel_id: str,
    content: str = "",
    embeds: list[dict] | None = None,
) -> bool:
    """
    Discord 채널에 메시지를 전송합니다.

    Args:
        bot_token: Discord Bot 토큰
        channel_id: 대상 채널 ID
        content: 일반 텍스트 메시지 (선택)
        embeds: Embed 리스트 (선택, 최대 10개)

    Returns:
        전송 성공 여부
    """
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    if not payload:
        logger.warning("전송할 내용이 없습니다.")
        return False

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            logger.info(f"메시지 전송 성공 (채널: {channel_id})")
            return True
        elif response.status_code == 429:
            # Rate limit 처리
            retry_after = response.json().get("retry_after", 5)
            logger.warning(f"Rate limit 도달. {retry_after}초 후 재시도...")
            time.sleep(retry_after)
            # 재시도
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                logger.info(f"재시도 성공 (채널: {channel_id})")
                return True

        logger.error(
            f"메시지 전송 실패 (채널: {channel_id}): "
            f"상태코드={response.status_code}, 응답={response.text}"
        )
        return False

    except requests.RequestException as e:
        logger.error(f"메시지 전송 중 오류 (채널: {channel_id}): {e}")
        return False


def send_daily_menu(
    bot_token: str,
    channel_id: str,
    header_content: str,
    embeds: list[dict],
) -> bool:
    """
    일간 식단 메시지를 전송합니다.
    Discord 한 메시지에 최대 10개 Embed를 넣을 수 있으므로,
    필요시 여러 메시지로 분할합니다.

    Args:
        bot_token: Discord Bot 토큰
        channel_id: 대상 채널 ID
        header_content: 헤더 텍스트 메시지
        embeds: 요일별 Embed 리스트

    Returns:
        전송 성공 여부
    """
    MAX_EMBEDS_PER_MESSAGE = 10

    if len(embeds) <= MAX_EMBEDS_PER_MESSAGE:
        # 한 메시지로 전송 가능
        return send_message(bot_token, channel_id, content=header_content, embeds=embeds)
    else:
        # 여러 메시지로 분할 (거의 발생하지 않음)
        success = send_message(bot_token, channel_id, content=header_content, embeds=embeds[:MAX_EMBEDS_PER_MESSAGE])
        if not success:
            return False

        time.sleep(1)  # Rate limit 방지

        remaining = embeds[MAX_EMBEDS_PER_MESSAGE:]
        return send_message(bot_token, channel_id, embeds=remaining)
