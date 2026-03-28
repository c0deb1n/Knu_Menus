import json
from src.scraper import fetch_menu_page
from src.parser import parse_weekly_menu

# 첨성관(37), 정보센터(35) 테스트
for shop_sqno in [37, 35]:
    print(f"--- shop_sqno: {shop_sqno} ---")
    html = fetch_menu_page(shop_sqno)
    if html:
        menu = parse_weekly_menu(html)
        print("Menu is empty?", menu.is_empty())
        print(json.dumps(menu.to_dict(), ensure_ascii=False, indent=2))
        print("\n")
