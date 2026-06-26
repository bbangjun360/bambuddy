# 3D Print Farm Harness-First Pack v1.2

이 패키지는 대형 명세를 Codex에 한 번에 넣는 방식을 버리고, **항상 실행 가능한
Bambuddy 기준선 위에 기능을 하나씩 붙이는 개발 방식**을 적용하기 위한 시작점이다.

## 개발 방식

이 프로젝트는 다음 네 가지를 결합한다.

1. **Walking Skeleton**  
   먼저 upstream Bambuddy를 수정하지 않은 상태로 실행·로그인·DB 저장·백업 복구까지
   성공시킨다.

2. **Vertical Slice**  
   한 PR은 “사용자가 확인할 수 있는 하나의 동작”만 추가한다. 예를 들어
   `STL 업로드 → Orca 슬라이싱 → 결과 파일 생성`이 하나의 수직 슬라이스다.

3. **Ports and Adapters**  
   ERPNext, PrintFlow, Obico는 Bambuddy 코어에 섞지 않고 API/adapter 경계로 연결한다.

4. **Harness-Driven Development**  
   기능을 만들기 전에 fake, fixture, contract, smoke test, fault scenario를 먼저 준비한다.

## Codex가 매 작업에 읽는 문서

Codex에게 전체 명세를 매번 주지 않는다.

```text
항상 자동 로드
└── AGENTS.md

현재 작업에서 명시적으로 읽음
├── docs/00_PROJECT_CHARTER.md
├── workpacks/WP-xxx.md
├── 관련 docs/modules/*.md
└── 필요 시 관련 contract/fixture

평상시 읽지 않음
└── docs/archive/FULL_SPEC_v1.1.md
```

## 첫 실행

이 패키지를 Bambuddy Fork의 루트에 복사한 뒤 다음 순서로 시작한다.

```bash
cp .env.harness.example .env.harness
# 이미지 변수는 반드시 버전과 digest로 교체한다.

python3 harness/scripts/check_context_budget.py
python3 harness/scripts/check_workpack.py workpacks/WP-000_BASELINE_AND_HARNESS.md
make harness-config
make harness-up
make harness-health
make verify-fast
```

`docker-compose.harness.yml`은 Bambuddy Fork 루트에 이 패키지가 복사된 것을 전제로 한다.
실제 upstream Dockerfile 및 환경변수 이름을 조사한 뒤 WP-000에서 최소 조정한다.

## 작업 순서

```text
WP-000  Bambuddy 기준선 + 하네스
WP-010  OrcaSlicer 수직 슬라이스
WP-020  관측성
WP-030  ERP Read Only
WP-040  ERP Draft Write
WP-050  베드 상태 머신 + Simulator
WP-060  PrintFlow 실제 장치 Canary
WP-070  Obico Shadow Mode
WP-080  자동 스케줄링 제약
```

각 Work Package가 끝날 때 시스템은 다시 실행 가능하고 이전 기능은 유지되어야 한다.
