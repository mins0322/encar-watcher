import json
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Keep the user's original Encar search URL and its exact filters.
SEARCH_URL = (
    r"https://www.encar.com/dc/dc_carsearchlist.do?carType=kor#!%7B%22action%22%3A%22"
    r"(And.Hidden.N.\_.(C.CarType.Y.\_.(C.Manufacturer.%ED%98%84%EB%8C%80.\_."
    r"(C.ModelGroup.%EC%95%84%EC%9D%B4%EC%98%A4%EB%8B%89.\_."
    r"(C.Model.%EB%8D%94%20%EB%89%B4%20%EC%95%84%EC%9D%B4%EC%98%A4%EB%8B%89%20%ED%95%98%EC%9D%B4%EB%B8%8C%EB%A6%AC%EB%93%9C.\_."
    r"(C.BadgeGroup.%EA%B0%80%EC%86%94%EB%A6%B0%2B%EC%A0%84%EA%B8%B0%201600cc.\_."
    r"(C.Badge.1\_.6%20%ED%94%8C%EB%9F%AC%EA%B7%B8%EC%9D%B8%20HEV._.BadgeDetail.Q.)))))))"
    r"%22%2C%22toggle%22%3A%7B%7D%2C%22layer%22%3A%22%22%2C%22sort%22%3A%22ModifiedDate%22%2C"
    r"%22page%22%3A1%2C%22limit%22%3A20%2C%22searchKey%22%3A%22%22%2C%22loginCheck%22%3Afalse%7D"
)

STATE_FILE = Path("seen_ids.json")
EMPTY_TEXTS = (
    "검색 결과가 없습니다",
    "검색된 차량이 없습니다",
    "조건에 맞는 차량이 없습니다",
    "검색 결과가 존재하지 않습니다",
)

def extract_listing_ids(page):
    """Extract listing IDs from detail links; fail closed if the page is unexpected."""
    page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(4000)

    # The search page is a legacy JS app; inspect rendered links after it has settled.
    hrefs = page.locator("a[href]").evaluate_all(
        "(els) => els.map(a => a.href).filter(Boolean)"
    )
    ids = set()
    for href in hrefs:
        decoded = unquote(href)
        # Typical Encar detail links include carid=12345678.
        for match in re.findall(r"(?:carid|carId|vehicleId|vehicleNo)[=/](\d{5,})", decoded, re.I):
            ids.add(match)

    body_text = page.locator("body").inner_text(timeout=10000)
    if ids:
        return ids

    if any(msg in body_text for msg in EMPTY_TEXTS):
        return set()

    # Do not treat a blocked page, redesign, or failed load as "zero listings".
    title = page.title()
    raise RuntimeError(
        f"매물 ID를 찾지 못했고 명확한 빈 검색 결과 문구도 없습니다. "
        f"페이지 제목={title!r}, 본문 앞부분={body_text[:500]!r}"
    )

def load_seen_ids():
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(str(x) for x in data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"{STATE_FILE} 읽기 실패: {exc}") from exc

def save_seen_ids(ids):
    STATE_FILE.write_text(
        json.dumps({"seen_ids": sorted(ids)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def send_email(new_count):
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("이메일 설정 환경변수가 없습니다: " + ", ".join(missing))

    sender = os.environ.get("EMAIL_FROM", os.environ["SMTP_USER"])
    msg = EmailMessage()
    msg["Subject"] = f"[엔카 감시] 신규 매물 {new_count}대 발견"
    msg["From"] = sender
    msg["To"] = os.environ["EMAIL_TO"]
    msg.set_content(
        f"설정한 엔카 검색 조건에서 신규 매물 {new_count}대를 발견했습니다.\n\n"
        f"매물별 상세 정보는 보내지 않았습니다. 아래 검색 결과에서 확인하세요.\n"
        f"{SEARCH_URL}\n"
    )

    port = int(os.environ["SMTP_PORT"])
    if port == 465:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=30) as smtp:
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(msg)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR")
        try:
            current_ids = extract_listing_ids(page)
        finally:
            browser.close()

    previous = load_seen_ids()

    # First successful run establishes a baseline without emailing existing listings.
    if previous is None:
        save_seen_ids(current_ids)
        print(f"초기 기준선 저장: {len(current_ids)}개 매물 ID")
        return

    new_ids = current_ids - previous
    # Save only after a successful search. Existing IDs are retained so temporary
    # disappearance/reappearance does not create repeated alerts.
    save_seen_ids(previous | current_ids)

    if new_ids:
        send_email(len(new_ids))
        print(f"신규 매물 {len(new_ids)}대 발견: 이메일 알림 발송")
    else:
        print(f"신규 매물 없음. 현재 검색 결과 {len(current_ids)}대")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
