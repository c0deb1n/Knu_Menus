"""
파싱된 메뉴 데이터를 Discord Embed 형식으로 변환합니다.
"""

from __future__ import annotations
from src.parser import WeeklyMenu, DayMenu, MealCategory, MealCorner

# 요일별 Embed 색상
DAY_COLORS = {
    "월": 0x57F287,  # 초록
    "화": 0x5865F2,  # 파랑
    "수": 0xFEE75C,  # 노랑
    "목": 0xE67E22,  # 주황
    "금": 0xED4245,  # 빨강
    "토": 0x9B59B6,  # 보라
    "일": 0x95A5A6,  # 회색
}

# 요일별 이모지
DAY_EMOJIS = {
    "월": "🟩",
    "화": "🟦",
    "수": "🟨",
    "목": "🟧",
    "금": "🟥",
    "토": "🟪",
    "일": "⬜",
}

# 식사 시간대 이모지
MEAL_EMOJIS = {
    "조식": "🌅",
    "중식": "🌞",
    "석식": "🌙",
}


def format_header_message(restaurant_name: str, restaurant_emoji: str, weekly_menu: WeeklyMenu) -> str:
    """
    주간 식단 헤더 메시지를 생성합니다.
    """
    if not weekly_menu.days:
        return f"{restaurant_emoji} **{restaurant_name}** 주간 식단표"

    first_day = weekly_menu.days[0]
    last_day = weekly_menu.days[-1]

    return (
        f"{restaurant_emoji} **{restaurant_name}** 주간 식단표\n"
        f"📅 {first_day.date}({first_day.day_name}) ~ {last_day.date}({last_day.day_name})"
    )


def format_weekly_embeds(restaurant_name: str, weekly_menu: WeeklyMenu) -> list[dict]:
    """
    주간 식단을 Discord Embed 리스트로 변환합니다.
    요일당 1개의 Embed를 생성합니다.

    Args:
        restaurant_name: 식당 이름
        weekly_menu: 파싱된 주간 메뉴

    Returns:
        Discord Embed JSON 딕셔너리 리스트 (최대 7개)
    """
    embeds = []

    for day in weekly_menu.days:
        embed = _format_day_embed(day)
        if embed:
            embeds.append(embed)

    return embeds


def _format_day_embed(day: DayMenu) -> dict | None:
    """
    하루 식단을 하나의 Discord Embed로 변환합니다.
    """
    if not day.meals:
        return None

    day_emoji = DAY_EMOJIS.get(day.day_name, "📅")
    color = DAY_COLORS.get(day.day_name, 0x95A5A6)

    fields = []

    # 같은 식사 시간대의 meals를 그룹핑
    meal_groups: dict[str, list[MealCategory]] = {}
    for meal in day.meals:
        category = meal.category or "기타"
        if category not in meal_groups:
            meal_groups[category] = []
        meal_groups[category].append(meal)

    for category_name, meals in meal_groups.items():
        meal_emoji = MEAL_EMOJIS.get(category_name, "🍴")
        field_value = _format_meal_field(meals)

        if field_value:
            fields.append({
                "name": f"{meal_emoji} {category_name}",
                "value": field_value[:1024],  # Discord 필드 제한
                "inline": True,
            })

    if not fields:
        return None

    embed = {
        "title": f"{day_emoji} {day.day_name}요일 · {day.date}",
        "color": color,
        "fields": fields,
        "footer": {"text": "경북대학교 생활협동조합"},
    }

    return embed


def _format_meal_field(meals: list[MealCategory]) -> str:
    """
    같은 시간대의 식사 코너들을 하나의 필드 텍스트로 포맷팅합니다.
    """
    lines: list[str] = []

    for meal in meals:
        for corner in meal.corners:
            # 코너명 표시 (일반이 아닌 경우에만)
            if corner.corner_name and corner.corner_name != "일반":
                lines.append(f"**{corner.corner_name}**")

            for item in corner.items:
                if item.price:
                    lines.append(f"• {item.name} {item.price}")
                else:
                    lines.append(f"• {item.name}")

            lines.append("")  # 코너 사이 빈 줄

    # 마지막 빈 줄 제거
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
