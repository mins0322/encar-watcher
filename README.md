# 엔카 신규 매물 이메일 감시

제공된 엔카 검색 URL을 10분 간격으로 열어 매물 ID를 확인하고, 새 ID가 생기면 신규 매물 수만 이메일로 알립니다. 매물별 상세 내용은 메일에 포함하지 않습니다.

## 동작 방식

- GitHub Actions에서 주기적으로 실행 (목표 주기 10분, 실제 실행은 지연될 수 있음)
- 검색 조건은 `watcher.py`의 `SEARCH_URL`에 제공된 URL 그대로 저장
- 첫 번째 성공 실행은 기준선만 저장하고 메일을 보내지 않음
- 이후 실행에서 새로 발견한 ID가 여러 개면 한 통의 이메일로 건수만 알림
- `seen_ids.json`에 ID를 저장하고 GitHub 저장소에 커밋해 실행 사이에 유지
- 검색 페이지를 읽지 못했거나 사이트 구조가 바뀐 경우 빈 결과로 간주하지 않고 실행을 실패시킴

## GitHub Actions 설정

1. GitHub에서 새 저장소를 만들고 이 폴더의 파일을 업로드/푸시합니다.
2. 저장소의 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 Secrets를 추가합니다.
3. **Actions** 탭에서 workflow를 활성화합니다.
4. **Run workflow**를 한 번 수동 실행해 로그를 확인합니다. 첫 실행은 기준선 저장이 목적입니다.

필수 Secrets:

| Secret | 설명 | 예시 |
|---|---|---|
| `SMTP_HOST` | 이메일 SMTP 서버 | Gmail: `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 포트 | Gmail SSL: `465`, STARTTLS: `587` |
| `SMTP_USER` | 발신 이메일 주소/계정 | 본인 Gmail 주소 |
| `SMTP_PASSWORD` | SMTP 비밀번호 또는 앱 비밀번호 | Gmail은 일반 계정 비밀번호 대신 앱 비밀번호 권장 |
| `EMAIL_TO` | 알림을 받을 이메일 주소 | 수신 주소 |
| `EMAIL_FROM` | 선택 항목. 비우면 `SMTP_USER` 사용 | 발신 주소 |

### Gmail 사용 예

- `SMTP_HOST`: `smtp.gmail.com`
- `SMTP_PORT`: `465`
- `SMTP_USER`: 본인 Gmail 주소
- `SMTP_PASSWORD`: Google 계정에서 만든 앱 비밀번호
- `EMAIL_TO`: 알림 받을 주소

Google 계정에서 2단계 인증을 켜고 앱 비밀번호를 만들 수 있어야 합니다. 앱 비밀번호를 코드나 저장소 파일에 직접 적지 말고 GitHub Secrets에만 저장하세요.

## 주의 사항

- GitHub Actions는 24시간 켜진 프로세스가 아니라 예약 시점마다 실행되는 방식입니다. 10분 간격을 설정했지만 혼잡 상황에서는 지연될 수 있습니다.
- GitHub 예약 실행은 저장소 기본 브랜치의 workflow를 실행합니다. 공개 저장소는 60일간 활동이 없으면 예약 workflow가 비활성화될 수 있습니다.
- 엔카는 페이지 구조나 접근 정책을 변경할 수 있습니다. 이 경우 실행 로그에 오류가 남고, 잘못해서 “신규 매물 없음”으로 처리하지 않도록 했습니다.
- 첫 실행 이후에는 ID가 검색 결과에서 잠시 사라졌다 다시 나타나도 중복 알림을 줄이기 위해 기존 ID 기록을 유지합니다.
- 저장소에 `seen_ids.json`을 커밋하므로 저장소에 불필요한 개인정보를 넣지 마세요. 이메일 비밀번호는 반드시 Secrets에만 보관하세요.

## 로컬에서 테스트

Python 3.10 이상 권장:

```bash
pip install -r requirements.txt
python -m playwright install chromium
python watcher.py
```

이메일 환경변수까지 설정해야 신규 매물 발견 시 메일을 발송합니다.
