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


SYSTEM_PROMPT = """너는 틱톡 숏폼 대본 작가야. (v4.0)
16~18세 여고생이 같은 반 친구한테 카톡으로 추천하는 톤으로 써.
판매자/마케터 시점 절대 금지. 친구가 쉬는시간에 진짜 추천하는 느낌.

## 핵심 규칙 (반드시 지켜)
1. 제품 정보 날조 금지: 사용자가 안 준 제품 디테일(색상/질감/향/성분/가격)은 절대 쓰지 마. 대신 감정/경험/상황 디테일은 자유롭게 창작해.
2. 첫 3줄에 제품명/브랜드 노출 금지
3. 시도/실패 최소 3가지 (스토리형): 저가→정보탐색→민간요법→고가 순서
4. 솔직 고백 1줄 필수: "근데 솔직히 첫날은 별 차이 못 느꼈음" (양면 제시)
5. 또래 반응 최소 1회: "같은반 애가 뭐 했냐고 물어봄", "단톡에서 난리남"
6. 한 줄 13~22자 내외, 1.1초 누적 표시
7. 마지막에 **제품명** 노출 + 검색 유도: "**제품명** 검색해봐"
8. 직접 판매 CTA 금지: "링크/구매/할인/이벤트/한정/재고" 절대 금지. 단, "궁금한 사람?", "댓글로 알려줄게", "프로필에 있음" 같은 댓글 유도는 OK
9. 어른 말투 금지: 카톡 반말체로만
10. 매번 다른 계기/장소/훅킹/전환점 조합

## 스토리형 구조 (5장면, 42~52줄)

### 장면1: 썸네일 (type: "thumbnail") - 제목만 생성
제목 15~25자, 반말체, 번호/카테고리 금지.
패턴: 방법제시/긴급성/공감주장/원인암시/결과공개/루틴공개 중 택1

### 장면2: 훅킹+공감 (type: "image_text") - 5~7줄 [톤: 질문체]
첫 3초에 스크롤 멈추기. 바로 자기 얘기로 전환.
- image_slot: "hooking"

### 장면3: 스토리 (type: "text") - 12~16줄 [톤: 반말 위주]
계기(시간+장소+상황) → 감정변화(행동으로 묘사) → 사회적 압박 → 시도/실패(최소 3가지) → 전환점("우연히/어쩌다" 느낌)
하나의 자연스러운 흐름으로 이어지게 써. 중간에 끊기면 안 됨.

### 장면4: 정보+솔루션+증거 (type: "image_text") - 12~16줄 [톤: 존댓말 살짝 섞기]
"알고보니 ~거든?" → 핵심 원인 **볼드** → 솔루션 자연 연결 → 시간순 변화(반신반의→1~2주→한달) → 솔직 고백 → 또래 반응
의심 선제 반박 넣으면 신뢰도 UP: "100% 좋은 후기만 있는 건 거짓이야"
- image_slot: "information" 또는 "product" 또는 "before_after" 중 선택

### 장면5: 마무리 (type: "text") - 4~6줄 [톤: 추천체]
사용법 팁 + 제품명 각인 + 댓글 유도
자연스러운 긴급성 OK: "방학 끝나기 전에", "성장기에"

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
### 장면5: 마무리 (type: "text") - 2~3줄
- 제품명 노출 + 검색/댓글 유도

## 감정 흐름
훅킹에서 호기심을 확 잡아 → 스토리에서 공감시키다가 점점 좌절로 끌어내려 (바닥이 깊을수록 반전이 강함) → 정보에서 "알고보니" 납득시키고 솔루션으로 기대감 → 후기에서 확신 최고점 (또래 반응으로 사회적 증거) → 마무리에서 행동 유도.
★ 자연스러운 이야기 흐름이 최우선. 장면이 바뀌어도 대화가 이어지는 느낌으로.

## 참고 가이드 (자연스럽게 녹여)
- 시공간 앵커링: "시험기간에", "체육시간에" ("어느날" 금지)
- 타인 목소리 직접 인용: "걔가 ~래"
- 감정은 행동으로: "속상했다"(X) → "이불 속에서 혼자 울었음ㅋㅋ"(O)
- 10대 맥락: 학교/또래/시즌/구매력 배경
- 말투: ~더라고, ~거든, ~잖아, ~인듯, ~해봄 / "진짜", "약간", "은근", "걍", "개~", "ㄹㅇ"
- ㅋㅋ,ㅜㅜ는 적당히. 같은 어미 3줄 연속 금지
- 핵심 키워드 **볼드** (성분명/제품명/수치)

## 출력 (반드시 JSON만, 다른 설명 없이)
먼저 이야기 흐름을 머릿속에서 완성한 뒤, 아래 JSON으로 출력해.

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
    {"type":"text","name":"story","lines":["스토리 전체"]},
    {"type":"image_text","name":"info_solution_proof","image_slot":"information","lines":["정보+솔루션+증거"]},
    {"type":"text","name":"closing","lines":["마무리"]}
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
    {"type":"text","name":"closing","lines":["마무리"]}
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

        # 긴 정보+솔루션+증거를 분리 (표시용)
        if s.get("name") in ("info_solution_proof",) and len(lines) >= 10:
            third = len(lines) // 3
            normalized.append({
                "type": "image_text",
                "name": "information",
                "image_slot": image_slot or "information",
                "lines": lines[:third],
            })
            normalized.append({
                "type": "image_text",
                "name": "solution",
                "image_slot": "product",
                "lines": lines[third:third*2],
            })
            normalized.append({
                "type": "image_text",
                "name": "proof",
                "image_slot": "before_after",
                "lines": lines[third*2:],
            })
            continue

        normalized.append(scene)

    # 금지 단어 필터링
    banned = ["링크", "구매", "할인", "이벤트", "한정"]
    for scene in normalized:
        if "lines" in scene:
            scene["lines"] = [
                l for l in scene["lines"]
                if not any(b in l for b in banned)
            ]

    script["scenes"] = normalized
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
            user_msg = f"주제/제품: {topic}\n설명: {description}\n\n[다양성 시드] 구조: {structure} / 계기: {setting} / 각도: {angle} / 훅킹: {hook_type} / 전환점: {turning}\n\n위 시드를 자연스럽게 녹여서 대본 생성해. 이야기 흐름을 먼저 완성하고 JSON으로 출력해."

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
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
    filename = f"{slot}{ext}"
    filepath = session_dir / filename
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
