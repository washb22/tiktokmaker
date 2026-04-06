import json
import os
import uuid
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from flask import Flask, Response, render_template, request, send_from_directory

from generator import generate_video, get_available_fonts

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def json_response(data, status=200):
    return Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def get_client():
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


SYSTEM_PROMPT = """너는 틱톡 숏폼 대본 작가야. (v4.1)
16~18세 여고생이 같은 반 친구한테 카톡으로 추천하는 톤으로 써.
판매자/마케터 시점 절대 금지. 친구가 쉬는시간에 진짜 추천하는 느낌.

## 핵심 규칙 (반드시 지켜)
1. 제품 정보 날조 금지: 사용자가 안 준 제품 디테일(색상/질감/향/성분/가격)은 절대 쓰지 마. 대신 감정/경험/상황 디테일은 자유롭게 창작해.
2. 첫 3줄에 제품명/브랜드 노출 금지
3. 시도/실패 최소 3가지 (스토리형): 저가→정보탐색→민간요법→고가 순서
4. 솔직 고백 1줄 필수: "근데 솔직히 첫날은 별 차이 못 느꼈음" (양면 제시)
5. 사회적 증거 최소 1회: 단체동참/단톡반응/SNS인증/가족반응/이성반응/우연목격/수치증거 등 매번 다른 패턴
6. 한 줄 13~22자 내외, 1.1초 누적 표시
7. 마지막에 **제품명** 노출 + 검색 유도: "**제품명** 검색해봐"
8. 직접 판매 CTA 금지: "링크/구매/할인/이벤트/한정/재고" 절대 금지. 단, "궁금한 사람?", "댓글로 알려줄게", "프로필에 있음" 같은 댓글 유도는 OK
9. 어른 말투 금지: 카톡 반말체로만
10. 매번 다른 계기/장소/훅킹/전환점 조합
11. ★ 후반부(후기~마무리)도 전반부만큼 디테일하게 써. 급하게 끝내지 마.

## 스토리형 구조 (8장면, 46~58줄)

### 장면1: 썸네일 (type: "thumbnail") - 제목만 생성
제목 15~25자, 반말체, 번호/카테고리 금지.

### 장면2: 훅킹+공감 (type: "image_text") - 5~7줄 [톤: 질문체]
첫 3초에 스크롤 멈추기. 바로 자기 얘기로 전환.
- image_slot: "hooking"

### 장면3: 스토리 전반 (type: "text", name: "story_emotion") - 6~8줄 [톤: 반말]
계기(시간+장소+상황) → 감정변화(행동묘사) → 사회적 압박

### 장면4: 스토리 후반 (type: "text", name: "story_struggle") - 6~8줄 [톤: 반말]
시도/실패(최소 3가지) → 전환점("우연히/어쩌다" 느낌)

### 장면5: 원인/정보 (type: "image_text", name: "information") - 5~7줄 [톤: 존댓말 살짝]
"알고보니 ~거든?" → 핵심 원인 **볼드** → 기존 방법 한계
- image_slot: "information"

### 장면6: 솔루션 (type: "image_text", name: "solution") - 5~7줄 ★추천 과정을 깊게
[감정: 납득→기대]
★ 레퍼런스 영상 평균 3.2줄. 제품명만 던지지 말고 "왜 이걸 선택했는지"까지 써.
(1) 비교 경험 1~2줄: "이것저것 20개 이상 써봤는데", "해외직구 10만원짜리 쓰다가" → 다른건 왜 안됐는지
(2) 이 제품을 선택한 이유 1~2줄: "여성전용으로 나온거라", "논문 성분이 전부 들어가있음"
(3) 구체적 사용법 1~2줄: "아침저녁 세안후 바르기", "하루한알 삼켜먹으면 됨", "알약 못먹으면 씹어먹어도 됨"
- image_slot: "product"

### 장면7: 후기/증거 (type: "image_text", name: "proof") - 7~10줄 ★가장 중요한 파트
[감정: 기대→확신→사회적 확인 (감정 최고점)]
★ 레퍼런스 영상 평균 3.3줄이지만 디테일이 매우 높음. 아래 5단계 전부 넣어.
(1) 시간대별 변화 타임라인 2~3줄: "처음 2~3주 아무변화 없더니 → 한달째 확 체감 → 두달 먹으니까 어이없을정도"
(2) 구체적 수치/결과 1줄: "AA에서 B~C 정도", "원래색으로 돌아옴", "옛날사진이랑 지금사진 차이 확실히 남"
(3) 솔직 고백 1줄: "근데 솔직히 첫날은 별 차이 못느꼈음" (단점 1개 인정)
(4) 부작용 우려 해소 1~2줄: "30알씩 먹어야 부작용", "내 친구 4명 다 효과봤는데 부작용 0명"
(5) 사회적 증거 1~2줄: ★[다양성 시드]의 social_proof 유형을 참고하되, 대사는 직접 창작해.
  레퍼런스에서 발견된 사회적 증거의 원리:
  - 누군가 변화를 알아채는 순간 (누가? 어디서? 어떤 반응?)
  - 혼자 쓰던 게 집단으로 퍼지는 과정 (몇명? 어떤 경위로?)
  - 온라인/오프라인에서 우연히 마주치는 증거 (어디서? 어떤 상황?)
  - 구체적 숫자가 들어간 증거 (N명, N개, N일)
  ★ 매번 새로운 상황/인물/장소/반응을 조합해서 창작할 것.
  ★ 같은 문장을 두 번 이상 쓰면 실패.
- image_slot: "before_after"

### 장면8: 팁+마무리 (type: "text", name: "closing") - 5~7줄 ★급하게 끝내지 마
[감정: 확신 유지(85%)→행동 충동(95%) - 하강 없이 크레센도]
★ 레퍼런스 영상은 제품추천으로 끝나지 않고 추가 생활팁으로 "완전한 가이드" 느낌을 줌.
(1) 추가 생활팁 1~2줄: "선크림은 닥터지 50짜리 추천", "최대한 화장 연하게", "통풍되는 속옷 입어"
(2) 감정적 결과 1줄: "자신감도 엄청 붙고", "못입던 옷 다시 입게됨", "고민한게 민망할정도"
(3) 오프닝 고통 콜백 + 제품 각인 1~2줄: "나처럼 ~때문에 고민하는 사람은 **제품명** 꼭 써봐!!!!"
(4) 클로징 마무리 1줄: ★[다양성 시드]의 closing_type을 참고하되, 대사는 직접 창작해.
  클로징의 원리:
  - 시청자에게 행동을 유도하는 한마디 (도전/약속/경고/호기심/긴급감 중 택1)
  - 스토리 전체 톤과 어울리는 자연스러운 마무리
  ★ 매번 새로운 마무리를 창작할 것. 같은 문장 반복 금지.

## 리스트형 구조 (5장면, 19~28줄)

### 장면1: 썸네일 - 위와 동일
### 장면2: 훅킹 (type: "image_text") - 3~4줄
- image_slot: "hooking"
### 장면3: 번호리스트 (type: "image_text") - 10~15줄
- "1. ~~ 2. ~~ 3. ~~" 형태. 중간에 제품 자연삽입
- 반대 의견 나올 수 있는 포인트 1개 넣으면 댓글 폭발
- image_slot: "list_items"
### 장면4: 증거 (type: "image_text") - 3~5줄
- 솔직 고백 1줄 필수
- image_slot: "before_after"
### 장면5: 마무리 (type: "text") - 3~4줄
- 제품명 노출 2회 이상 + 검색/댓글 유도

## 감정 흐름
훅킹→공감→좌절(바닥)→납득→기대→확신(최고점)→행동충동
★ 레퍼런스 분석 결과: 후반부(솔루션+증거+마무리)가 전체의 52%를 차지함.
★ 후반부가 전반부보다 짧으면 실패한 대본. 장면6-7-8에 총 17~24줄 배정할 것.
★ 특히 솔루션은 "왜 이걸 선택했는지" 비교경험+사용법까지, 증거는 시간대별 변화+부작용해소+사회증거까지.

## 참고 가이드
- 시공간 앵커링: "시험기간에", "체육시간에" ("어느날" 금지)
- 타인 목소리 직접 인용: "걔가 ~래"
- 감정은 행동으로: "속상했다"(X) → "이불 속에서 혼자 울었음ㅋㅋ"(O)
- 10대 맥락: 학교/또래/시즌/구매력 배경
- 말투: ~더라고, ~거든, ~잖아, ~인듯, ~해봄 / "진짜", "약간", "은근", "걍", "개~", "ㄹㅇ"
- ㅋㅋ,ㅜㅜ는 적당히. 같은 어미 3줄 연속 금지
- 핵심 키워드 **볼드** (성분명/제품명/수치)

## 출력 (반드시 JSON만, 다른 설명 없이)
먼저 이야기 흐름을 머릿속에서 완성한 뒤, 아래 JSON으로 출력해.
★ 출력 전 자기검증 (하나라도 실패하면 다시 써):
1. 장면6(솔루션)에 비교경험+사용법이 있는가?
2. 장면7(증거)에 시간대별 변화 타임라인이 있는가?
3. 장면7에 부작용 해소 또는 솔직고백이 있는가?
4. 장면8(마무리)에 추가 생활팁이 있는가?
5. 장면8에 감정적 결과(삶의 변화)가 있는가?
6. 후반부(장면6+7+8) 합계가 17줄 이상인가?

스토리형:
```json
{
  "title": "영상 제목",
  "thumbnail_title": "썸네일 제목",
  "structure_type": "story",
  "perspective": "first_person 또는 third_person",
  "scenes": [
    {"type":"thumbnail","title":"제목","duration":2.5},
    {"type":"image_text","name":"hooking","image_slot":"hooking","lines":["줄1","줄2"]},
    {"type":"text","name":"story_emotion","lines":["스토리 전반"]},
    {"type":"text","name":"story_struggle","lines":["스토리 후반"]},
    {"type":"image_text","name":"information","image_slot":"information","lines":["원인/정보"]},
    {"type":"image_text","name":"solution","image_slot":"product","lines":["솔루션"]},
    {"type":"image_text","name":"proof","image_slot":"before_after","lines":["후기 7~10줄"]},
    {"type":"text","name":"closing","lines":["팁+마무리 6~8줄"]}
  ]
}
```

리스트형:
```json
{
  "title": "영상 제목",
  "thumbnail_title": "썸네일 제목",
  "structure_type": "list",
  "scenes": [
    {"type":"thumbnail","title":"제목","duration":2.5},
    {"type":"image_text","name":"hooking","image_slot":"hooking","lines":["줄1","줄2"]},
    {"type":"image_text","name":"list_items","image_slot":"list_items","lines":["1. 첫번째","2. 두번째"]},
    {"type":"image_text","name":"proof","image_slot":"before_after","lines":["후기"]},
    {"type":"text","name":"closing","lines":["마무리 3~4줄"]}
  ]
}
```"""


IMAGE_SLOT_NAMES = {"hooking", "product", "before_after", "information", "list_items"}


def normalize_script(script):
    """AI 응답을 일관된 형식으로 변환"""
    raw_scenes = script.get("scenes", [])
    normalized = []

    # 썸네일 추가 (없으면 생성)
    has_thumbnail = any(s.get("type") == "thumbnail" for s in raw_scenes)
    if not has_thumbnail:
        normalized.append({
            "type": "thumbnail",
            "title": script.get("thumbnail_title", script.get("title", "제목")),
            "duration": 2.5,
        })

    for s in raw_scenes:
        if s.get("type") == "thumbnail":
            # 19)) 등 카테고리 번호 prefix 제거
            import re
            title = s.get("title", "")
            title = re.sub(r'^\d+\)\)\s*', '', title)
            s["title"] = title
            s.pop("category", None)
            normalized.append(s)
            continue

        # text → lines 변환
        lines = s.get("lines", [])
        if not lines and s.get("text"):
            lines = [l.strip() for l in s["text"].split("\n") if l.strip()]

        # type 자동 결정
        image_slot = s.get("image_slot", "")
        scene_type = "image_text" if image_slot in IMAGE_SLOT_NAMES else "text"

        scene = {
            "type": scene_type,
            "name": s.get("name", ""),
            "lines": lines,
        }
        if image_slot:
            scene["image_slot"] = image_slot

        # 긴 스토리를 전반/후반으로 자동 분리 (표시용)
        if s.get("name") in ("story", "story_full") and len(lines) >= 10:
            mid = len(lines) // 2
            normalized.append({
                "type": "text",
                "name": "story_emotion",
                "lines": lines[:mid],
            })
            normalized.append({
                "type": "text",
                "name": "story_struggle",
                "lines": lines[mid:],
            })
            continue

        # 레거시: 합쳐진 info_solution_proof가 오면 40/30/30으로 분리 (proof에 더 비중)
        if s.get("name") in ("info_solution_proof",) and len(lines) >= 10:
            info_end = max(3, len(lines) * 3 // 10)
            sol_end = info_end + max(3, len(lines) * 3 // 10)
            normalized.append({
                "type": "image_text",
                "name": "information",
                "image_slot": image_slot or "information",
                "lines": lines[:info_end],
            })
            normalized.append({
                "type": "image_text",
                "name": "solution",
                "image_slot": "product",
                "lines": lines[info_end:sol_end],
            })
            normalized.append({
                "type": "image_text",
                "name": "proof",
                "image_slot": "before_after",
                "lines": lines[sol_end:],
            })
            continue

        normalized.append(scene)

    # 레거시: tips+closing이 분리되어 오면 합쳐서 하나의 closing으로
    merged = []
    i = 0
    while i < len(normalized):
        s = normalized[i]
        if s.get("name") == "tips" and i + 1 < len(normalized) and normalized[i + 1].get("name") == "closing":
            merged.append({
                "type": "text",
                "name": "closing",
                "lines": s.get("lines", []) + normalized[i + 1].get("lines", []),
            })
            i += 2
            continue
        merged.append(s)
        i += 1
    normalized = merged

    # 금지 단어 필터링
    banned = ["링크", "구매", "할인", "이벤트", "한정"]
    for scene in normalized:
        if "lines" in scene:
            scene["lines"] = [
                l for l in scene["lines"]
                if not any(b in l for b in banned)
            ]

    # 후반부 디테일 검증: proof/closing이 너무 짧으면 경고 플래그
    for scene in normalized:
        name = scene.get("name", "")
        lines = scene.get("lines", [])
        if name == "proof" and len(lines) < 5:
            scene["_warning"] = "proof_too_short"
        if name == "closing" and len(lines) < 4:
            scene["_warning"] = "closing_too_short"

    script["scenes"] = normalized
    return script


ENHANCE_PROMPT = """너는 틱톡 숏폼 대본의 후반부(솔루션+후기+마무리)만 보강하는 전문 에디터야.
16~18세 여고생 카톡 말투. 한 줄 13~22자.

아래 대본의 후반부가 너무 얇아. 전반부 맥락을 참고해서 후반부 3개 장면을 더 풍부하게 다시 써줘.
★ 기존 후반부를 복붙하지 말고, 같은 맥락에서 완전히 새로 창작해.

## 보강 규칙
[solution] 5~7줄:
- 다른 방법들과 비교한 경험 1~2줄 (왜 이게 나은지)
- 이 제품을 선택한 이유 1~2줄 (성분/원리/지인추천 등)
- 구체적 사용법 1~2줄 (시간/횟수/방법 - 디테일하게)

[proof] 8~10줄 ★가장 중요 - 전부 새로 창작:
- 시간대별 변화 타임라인 2~3줄 (구체적 기간+변화 묘사)
- 구체적 수치/비포애프터 1줄 (사이즈/색상/사진 비교 등)
- 솔직 고백 1줄 (완벽하진 않은 부분 인정)
- 부작용/우려 해소 1~2줄 (구체적 숫자와 함께)
- 사회적 증거 1~2줄: ★지시된 유형을 참고하되 대사는 창작.
  원리: 누군가 변화를 알아채거나, 혼자→집단으로 퍼지는 과정.
  매번 다른 인물/장소/상황/반응을 조합해서 새로 만들 것.

[closing] 5~7줄:
- 추가 생활팁 1~2줄 (제품 외 무료 관리법 - 구체적 브랜드/방법)
- 감정적 결과 1줄 (제품효과가 아닌 삶의 변화)
- 고통 콜백 + 제품 확신 1~2줄 (**제품명** 2회 이상)
- 클로징 마무리 1줄: ★지시된 유형을 참고하되 대사는 창작.
  원리: 시청자에게 행동을 유도하는 자연스러운 한마디.

## 출력: JSON만 (설명 없이)
{"solution":["줄1","줄2",...], "proof":["줄1","줄2",...], "closing":["줄1","줄2",...]}
"""


def _enhance_back_half(client, script, topic, description):
    """후반부가 짧으면 별도 API 호출로 보강"""
    import random

    scenes = script.get("scenes", [])
    proof_scene = next((s for s in scenes if s.get("name") == "proof"), None)
    closing_scene = next((s for s in scenes if s.get("name") == "closing"), None)
    solution_scene = next((s for s in scenes if s.get("name") == "solution"), None)

    proof_len = len(proof_scene.get("lines", [])) if proof_scene else 0
    closing_len = len(closing_scene.get("lines", [])) if closing_scene else 0
    solution_len = len(solution_scene.get("lines", [])) if solution_scene else 0
    back_total = proof_len + closing_len + solution_len

    # 후반부 합계 17줄 이상이면 OK
    if back_total >= 17:
        return script

    # 전반부 텍스트 요약
    front_lines = []
    for s in scenes:
        if s.get("name") in ("hooking", "story_emotion", "story_struggle", "information"):
            front_lines.extend(s.get("lines", []))
    front_summary = "\n".join(front_lines[:15])

    # 기존 후반부
    sol_lines = solution_scene.get("lines", []) if solution_scene else []
    proof_lines = proof_scene.get("lines", []) if proof_scene else []
    closing_lines = closing_scene.get("lines", []) if closing_scene else []

    social_proof = random.choice([
        "누군가 직접 물어보는 상황",
        "혼자→여러명으로 퍼지는 과정",
        "온라인 반응 폭발",
        "가족이 변화를 알아챔",
        "이성이 반응하는 장면",
        "우연히 같은 제품 쓰는 사람 마주침",
        "구체적 숫자로 증명 (N명/N일)",
        "아는 사람만 아는 비밀 공유",
    ])
    closing_type = random.choice([
        "댓글 소통 유도",
        "기간 도전 제안",
        "의심에 반론",
        "주의사항 경고",
        "품절/시기 긴급감",
        "비밀 공유 느낌",
    ])

    enhance_msg = f"""주제: {topic}
설명: {description}

[전반부 맥락]
{front_summary}

[현재 후반부 - 너무 짧아서 보강 필요]
solution ({solution_len}줄): {json.dumps(sol_lines, ensure_ascii=False)}
proof ({proof_len}줄): {json.dumps(proof_lines, ensure_ascii=False)}
closing ({closing_len}줄): {json.dumps(closing_lines, ensure_ascii=False)}

★ 사회적 증거 패턴: {social_proof}
★ 클로징 패턴: {closing_type}
★ "같은반 애가 물어봄" 패턴 사용 금지. 위에 지정된 패턴만 써.

위 후반부를 규칙에 맞게 풍부하게 다시 써줘. solution 5~7줄, proof 8~10줄, closing 5~7줄."""

    try:
        msg2 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            temperature=0.8,
            system=ENHANCE_PROMPT,
            messages=[{"role": "user", "content": enhance_msg}],
        )
        resp2 = msg2.content[0].text.strip()
        if "```json" in resp2:
            resp2 = resp2.split("```json")[1].split("```")[0].strip()
        elif "```" in resp2:
            resp2 = resp2.split("```")[1].split("```")[0].strip()

        enhanced = json.loads(resp2)

        # 보강된 내용으로 직접 교체
        for s in script["scenes"]:
            sname = s.get("name", "")
            if sname == "solution" and enhanced.get("solution"):
                s["lines"] = enhanced["solution"]
            elif sname == "proof" and enhanced.get("proof"):
                s["lines"] = enhanced["proof"]
            elif sname == "closing" and enhanced.get("closing"):
                s["lines"] = enhanced["closing"]

    except Exception:
        pass  # 보강 실패해도 원본 유지

    return script


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate-script", methods=["POST"])
def generate_script():
    data = request.json
    topic = data.get("topic", "")
    description = data.get("description", "")
    direction = data.get("direction", "")

    if not topic:
        return json_response({"error": "주제를 입력해주세요"}, 400)

    try:
        client = get_client()
        import random

        if direction:
            # 사용자가 방향을 지정한 경우 - 그 방향대로 생성
            user_msg = f"주제/제품: {topic}\n설명: {description}\n\n★ 대본 방향 지시: {direction}\n위 방향에 맞춰서 대본을 생성해. 썸네일 제목, 훅킹, 스토리 전개 모두 이 방향에 맞게. 사용자가 안 준 제품 정보는 절대 지어내지 마."
        else:
            # 방향 미지정 - 랜덤 다양성 시드
            setting = random.choice([
                "체육시간", "수영장", "영상통화", "수학여행", "졸업앨범",
                "소개팅", "셀카찍다가", "찜질방", "교복피팅", "SNS댓글",
                "단톡방사진", "방학모임", "알바면접", "생일파티", "축제준비",
                "학원끝나고", "급식시간", "수능끝나고", "교회수련회", "캠핑",
            ])
            angle = random.choice([
                "본인 시점으로", "친구 이야기로(3자 시점)", "엄마 반응 포함",
                "남사친/여사친 반응 포함", "단톡방 대화 인용", "SNS 댓글 반응 포함",
            ])
            hook_type = random.choice([
                "공감확인형", "참여형질문", "학교상황",
                "노력최소화형", "충격반전형", "결과먼저공개형",
            ])
            turning = random.choice([
                "인스타광고로", "친구추천으로", "커뮤글 보고",
                "틱톡영상 보고", "언니추천으로", "알바선배가 알려줘서",
                "유튜브 보다가", "엄마가 사다줘서",
            ])
            structure = random.choice(["스토리형", "스토리형", "스토리형", "리스트형"])
            social_proof = random.choice([
                "누군가 직접 물어보는 상황 - 어디서 누가 어떤 반응으로?",
                "혼자 쓰던 게 여러명으로 퍼지는 과정 - 몇명이 어떻게?",
                "온라인에서 반응이 폭발하는 순간 - 어떤 플랫폼에서?",
                "가족이 변화를 알아채는 장면 - 누가 뭐라고?",
                "이성이 반응하는 장면 - 어떤 상황에서?",
                "우연히 같은 제품 쓰는 사람을 마주치는 상황",
                "구체적 숫자로 증명하는 방식 - N명, N일, N%",
                "비밀처럼 공유되는 느낌 - 아는 사람만 아는",
            ])
            closing_type = random.choice([
                "댓글로 소통 유도",
                "기간 도전 제안 (N일/N주만 해봐)",
                "의심하는 사람에게 반론",
                "주의사항/꿀팁 경고",
                "품절/시기 긴급감",
                "비밀 공유하는 느낌",
            ])
            user_msg = f"주제/제품: {topic}\n설명: {description}\n\n[다양성 시드] 구조: {structure} / 계기: {setting} / 각도: {angle} / 훅킹: {hook_type} / 전환점: {turning} / 사회적증거: {social_proof} / 클로징: {closing_type}\n\n위 시드를 자연스럽게 녹여서 대본 생성해. 이야기 흐름을 먼저 완성하고 JSON으로 출력해."

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=5500,
            temperature=0.85,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": user_msg,
                }
            ],
        )

        response_text = message.content[0].text.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        script = json.loads(response_text)
        script = normalize_script(script)

        # 2단계: 후반부 보강 - proof/closing이 짧으면 별도 호출로 확장
        try:
            script = _enhance_back_half(client, script, topic, description)
        except Exception:
            pass  # 보강 실패해도 원본 반환

        return json_response(script)

    except json.JSONDecodeError:
        return json_response({"error": "대본 생성 실패 - 다시 시도해주세요"}, 500)
    except anthropic.AuthenticationError:
        return json_response({"error": "API 키가 올바르지 않습니다. .env 파일을 확인해주세요"}, 401)
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/api/upload-image", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return json_response({"error": "파일 없음"}, 400)

    file = request.files["file"]
    slot = request.form.get("slot", "general")
    session_id = request.form.get("session_id", uuid.uuid4().hex[:8])

    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(exist_ok=True)

    ext = Path(file.filename).suffix or ".png"
    timestamp = uuid.uuid4().hex[:6]
    filename = f"{slot}_{timestamp}{ext}"
    filepath = session_dir / filename
    # 기존 같은 슬롯 파일 삭제
    for old in session_dir.glob(f"{slot}_*"):
        old.unlink(missing_ok=True)
    for old in session_dir.glob(f"{slot}.*"):
        old.unlink(missing_ok=True)
    file.save(str(filepath))

    return json_response(
        {
            "path": str(filepath),
            "url": f"/uploads/{session_id}/{filename}",
            "slot": slot,
        }
    )


@app.route("/uploads/<path:filepath>")
def serve_upload(filepath):
    return send_from_directory(str(UPLOAD_DIR), filepath)


@app.route("/api/generate-video", methods=["POST"])
def generate_video_api():
    data = request.json
    scenes_data = data.get("scenes", [])

    if not scenes_data:
        return json_response({"error": "장면 데이터가 없습니다"}, 400)

    # 장면 데이터 변환
    scenes = []
    for scene in scenes_data:
        s = {
            "type": scene.get("type", "text"),
        }
        if scene.get("type") == "thumbnail":
            s["title"] = scene.get("title", "")
            s["category"] = scene.get("category", "19")
            s["duration"] = scene.get("duration", 2.5)
        else:
            # lines_data 형식 (스타일 + 이미지 포함)
            s["lines_data"] = scene.get("lines_data", [])
            if not s["lines_data"] and scene.get("lines"):
                s["lines_data"] = [{"text": l, "style": {}} for l in scene["lines"]]

        image_path = scene.get("image_path", "")
        if image_path and os.path.exists(image_path):
            s["image_path"] = image_path

        scenes.append(s)

    try:
        output_path = generate_video(scenes, str(OUTPUT_DIR))
        filename = os.path.basename(output_path)
        return json_response(
            {"video_url": f"/output/{filename}", "filename": filename}
        )
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/output/<filename>")
def serve_output(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


@app.route("/api/fonts")
def fonts_list():
    return json_response(get_available_fonts())


@app.route("/api/bgm-list")
def bgm_list():
    bgm_dir = BASE_DIR / "static" / "bgm"
    files = [f.name for f in bgm_dir.glob("*.mp3")]
    return json_response(files)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=False)
