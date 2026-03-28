"""
KNU 생협 식단 HTML 파서

생협 사이트의 HTML 테이블을 구조화된 데이터로 변환합니다.

HTML 구조:
  div.week_table
    p.title → 식사 시간대 (조식/중식/석식)
    table.tstyle_me.tac
      thead → 요일/날짜 헤더
      tbody → 식단 데이터
        tr → 각 메뉴 행
          td → 요일별 셀
            div.button_m.bt_me01 → "특식" 라벨
            div.button_m.bt_me02 → "천원의 아침밥" 라벨
            ul.menu_im → 메뉴 리스트
              li → 개별 메뉴 아이템
                텍스트 → 메뉴명
                p → 가격 (￦ 기호)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# === 데이터 모델 ===

@dataclass
class MenuItem:
    """개별 메뉴 항목"""
    name: str          # 메뉴명 (예: "순살돈가스★")
    price: str = ""    # 가격 (예: "₩4,500")

    def to_dict(self) -> dict:
        return {"name": self.name, "price": self.price}


@dataclass
class MealCorner:
    """식사 코너 (예: 특식, 천원의 아침밥)"""
    corner_name: str           # 코너명 (예: "특식", "천원의 아침밥", "일반")
    items: list[MenuItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "corner_name": self.corner_name,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class MealCategory:
    """식사 시간대 (조식/중식/석식)"""
    category: str                    # "조식", "중식", "석식"
    corners: list[MealCorner] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "corners": [corner.to_dict() for corner in self.corners],
        }


@dataclass
class DayMenu:
    """하루 식단"""
    date: str            # "03/23"
    day_name: str        # "월"
    meals: list[MealCategory] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "day_name": self.day_name,
            "meals": [meal.to_dict() for meal in self.meals],
        }


@dataclass
class WeeklyMenu:
    """주간 식단"""
    days: list[DayMenu] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "days": [day.to_dict() for day in self.days],
        }

    def is_empty(self) -> bool:
        """식단 데이터가 있는지 확인"""
        return len(self.days) == 0 or all(
            len(day.meals) == 0 for day in self.days
        )


# === 파싱 함수 ===

def parse_weekly_menu(html: str) -> WeeklyMenu:
    """
    생협 식단 HTML을 파싱하여 WeeklyMenu 객체를 반환합니다.

    Args:
        html: 생협 식단 페이지의 전체 HTML

    Returns:
        WeeklyMenu 객체
    """
    soup = BeautifulSoup(html, "html.parser")
    weekly_menu = WeeklyMenu()

    # 식사 시간대별 테이블 블록 찾기 (div.week_table)
    week_tables = soup.find_all("div", class_="week_table")

    if not week_tables:
        # week_table이 없으면 직접 테이블 찾기 시도
        tables = soup.find_all("table", class_="tstyle_me")
        if not tables:
            logger.warning("식단 테이블을 찾을 수 없습니다.")
            return weekly_menu
        # 테이블이 직접 있는 경우 처리
        for table in tables:
            _parse_meal_table(table, None, weekly_menu)
        return weekly_menu

    for block in week_tables:
        # 식사 시간대 타이틀 (p.title)
        title_elem = block.find("p", class_="title")
        meal_category_name = title_elem.get_text(strip=True) if title_elem else ""

        # 테이블 찾기
        table = block.find("table", class_="tstyle_me")
        if not table:
            continue

        _parse_meal_table(table, meal_category_name, weekly_menu)

    return weekly_menu


def _parse_meal_table(table: Tag, meal_category_name: str | None, weekly_menu: WeeklyMenu):
    """
    하나의 식사 시간대 테이블을 파싱합니다.
    """
    # 헤더에서 요일/날짜 정보 추출
    thead = table.find("thead")
    if not thead:
        return

    headers = []
    th_tags = thead.find_all("th")
    for th in th_tags:
        text = th.get_text(strip=True)
        # "월(03/23)" 형태에서 요일과 날짜 추출
        match = re.match(r"([월화수목금토일])\s*\((\d{2}/\d{2})\)", text)
        if match:
            headers.append({
                "day_name": match.group(1),
                "date": match.group(2),
            })

    if not headers:
        return

    # 각 헤더(요일)에 대응하는 DayMenu가 weekly_menu에 이미 있는지 확인, 없으면 생성
    day_map: dict[int, DayMenu] = {}
    for i, header in enumerate(headers):
        existing = None
        for day in weekly_menu.days:
            if day.date == header["date"] and day.day_name == header["day_name"]:
                existing = day
                break
        if existing:
            day_map[i] = existing
        else:
            new_day = DayMenu(date=header["date"], day_name=header["day_name"])
            weekly_menu.days.append(new_day)
            day_map[i] = new_day

    # tbody 행(row) 파싱
    tbody = table.find("tbody")
    if not tbody:
        return

    rows = tbody.find_all("tr")
    for row in rows:
        cells = row.find_all("td")

        # 셀 수가 헤더와 맞지 않으면 스킵
        if len(cells) < len(headers):
            continue

        # 각 요일별 셀 처리
        for col_idx, header in enumerate(headers):
            # 첫 번째 컬럼이 "분류"(조식/중식 등) 텍스트인 경우가 있어
            # 실제 데이터 셀의 인덱스를 조정해야 할 수 있음
            cell_idx = col_idx
            if len(cells) > len(headers):
                cell_idx = col_idx + (len(cells) - len(headers))

            if cell_idx >= len(cells):
                continue

            cell = cells[cell_idx]
            corners = _parse_cell(cell)

            if corners:
                meal = MealCategory(
                    category=meal_category_name or "",
                    corners=corners,
                )
                day_map[col_idx].meals.append(meal)


def _parse_cell(cell: Tag) -> list[MealCorner]:
    """
    하나의 테이블 셀(td)에서 메뉴 정보를 추출합니다.

    셀 내부 구조:
    - div.button_m → 코너 라벨 (특식, 천원의 아침밥)
    - ul.menu_im → 메뉴 리스트
      - li → 개별 메뉴
        - 텍스트 → 메뉴명
        - p → 가격(￦) 또는 부가 정보
    """
    corners: list[MealCorner] = []

    # 셀이 비어있는지 확인
    cell_text = cell.get_text(strip=True)
    if not cell_text:
        return corners

    # 코너 라벨 찾기
    corner_labels = cell.find_all("div", class_="button_m")

    # 메뉴 리스트 찾기
    menu_lists = cell.find_all("ul", class_="menu_im")

    if not menu_lists and not corner_labels:
        # 구조화된 태그가 없으면 텍스트에서 직접 파싱 시도
        items = _parse_text_menu(cell)
        if items:
            corners.append(MealCorner(corner_name="일반", items=items))
        return corners

    # 코너 라벨과 메뉴 리스트를 매핑
    # 보통 라벨 다음에 오는 메뉴 리스트가 해당 코너의 메뉴
    if corner_labels and menu_lists:
        # 코너가 있는 경우: 코너별로 그룹핑
        current_corner_name = "일반"
        current_items: list[MenuItem] = []

        for child in cell.children:
            if isinstance(child, Tag):
                if "button_m" in child.get("class", []):
                    # 이전 코너 저장
                    if current_items:
                        corners.append(MealCorner(
                            corner_name=current_corner_name,
                            items=current_items,
                        ))
                        current_items = []
                    current_corner_name = child.get_text(strip=True)

                elif child.name == "ul" and "menu_im" in child.get("class", []):
                    items = _parse_menu_list(child)
                    current_items.extend(items)

        # 마지막 코너 저장
        if current_items:
            corners.append(MealCorner(
                corner_name=current_corner_name,
                items=current_items,
            ))

    elif menu_lists:
        # 코너 없이 메뉴만 있는 경우
        all_items = []
        for menu_list in menu_lists:
            all_items.extend(_parse_menu_list(menu_list))
        if all_items:
            corners.append(MealCorner(corner_name="일반", items=all_items))

    return corners


def _parse_menu_list(ul: Tag) -> list[MenuItem]:
    """
    ul.menu_im 내의 li 목록을 파싱합니다.
    """
    items: list[MenuItem] = []
    li_tags = ul.find_all("li")

    for li in li_tags:
        item = _parse_menu_item(li)
        if item:
            items.append(item)

    return items


def _parse_menu_item(li: Tag) -> MenuItem | None:
    """
    하나의 li 태그에서 메뉴명과 가격을 추출합니다.

    li 내부 구조:
    - 직접 텍스트: 메뉴명 (br 태그로 줄바꿈될 수 있음)
    - p 태그: 가격 (￦ 포함) 또는 부가 메뉴
    """
    # 가격 정보 찾기 (p 태그 중 ￦ 포함하는 것)
    price = ""
    price_tags = li.find_all("p")
    non_price_texts = []

    for p in price_tags:
        p_text = p.get_text(strip=True)
        if "￦" in p_text or "₩" in p_text:
            price = _normalize_price(p_text)
        else:
            # 가격이 아닌 p 태그 텍스트는 부가 메뉴
            if p_text:
                non_price_texts.append(p_text)

    # 메뉴명 추출 (li의 직접 텍스트 + br로 구분된 텍스트)
    # p 태그를 제거한 나머지 텍스트
    menu_parts = []
    for child in li.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                menu_parts.append(text)
        elif isinstance(child, Tag):
            if child.name == "br":
                continue
            elif child.name != "p":
                text = child.get_text(strip=True)
                if text:
                    menu_parts.append(text)

    # 부가 메뉴 텍스트 합치기
    menu_parts.extend(non_price_texts)
    menu_name = " ".join(menu_parts).strip()

    if not menu_name:
        return None

    # 메뉴명에 포함된 시간 정보 정리
    menu_name = _clean_menu_name(menu_name)

    return MenuItem(name=menu_name, price=price)


def _parse_text_menu(cell: Tag) -> list[MenuItem]:
    """
    구조화된 태그 없이 텍스트로만 된 메뉴를 파싱합니다.
    (폴백 파서)
    """
    items = []
    text = cell.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    current_name = []
    for line in lines:
        if "￦" in line or "₩" in line:
            price = _normalize_price(line)
            name = " ".join(current_name) if current_name else ""
            if name:
                items.append(MenuItem(name=_clean_menu_name(name), price=price))
            current_name = []
        else:
            current_name.append(line)

    # 가격 없는 마지막 메뉴
    if current_name:
        name = " ".join(current_name)
        items.append(MenuItem(name=_clean_menu_name(name), price=""))

    return items


def _normalize_price(price_text: str) -> str:
    """가격 문자열을 통일된 형식으로 변환"""
    # "￦ 6,500" → "₩6,500"
    price = price_text.strip()
    price = price.replace("￦", "₩").replace(" ", "")
    return price


def _clean_menu_name(name: str) -> str:
    """메뉴명 정리"""
    # 불필요한 공백 정리
    name = re.sub(r"\s+", " ", name).strip()
    return name
