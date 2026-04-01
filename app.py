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


SYSTEM_PROMPT = """너는 틱톡 숏폼 영상 대본 작성 전문가야.
사용자가 주제/제품을 입력하면 아래 구조에 맞춰 대본을 생성해.

## 화자 설정
화자는 16~18세 한국 여고생이다. 직접 써보고 솔직하게 후기를 올리는 톤.
절대 판매자/마케터 시점이 아닌, 같은 반 친구가 쉬는시간에 카톡으로 추천하는 느낌.

## 핵심 규칙
- 대본은 "한 줄" 단위. 한 줄은 15~25자 내외.
- 한 줄당 1.1초씩 화면에 누적 표시됨.
- 총 45~55줄 (약 50~60초 영상)
- 장면 전환 시 이전 텍스트는 사라지고 새 장면 시작

## 10대 타겟 필수 규칙
1. "우리반", "우리학교", "급식", "쉬는시간", "야자" 같은 학교 배경을 반드시 1~2줄 넣어
2. 또래 반응 최소 1회 포함: "같은반 애가 뭐 했냐고 물어봄", "단톡에서 난리남"
3. 10대 구매력 고려: "용돈으로 삼", "다이소 가격", "개쌈" 등 가격 현실성
4. 방학/시험/수학여행 등 10대 시즌 이벤트 활용: "시험 끝나고", "수학여행 전에"

## 영상 구조 (8단계 감정 곡선)

### 장면1: 썸네일 (type: "thumbnail") - 1줄
- 네이트판/에타 게시글 스타일
- "19)) ~~한 사람 나만 그래?" 식 자극적 제목
- 실제 커뮤니티 고민글처럼

### 장면2: 훅킹 + 공감 (type: "image_text") - 5~7줄
[감정: 호기심 → 공감]
- 첫 줄은 반드시 스크롤 멈추는 한마디:
  * 공감확인: "너네도 코 블랙헤드 때문에 스트레스받지?"
  * 노력최소화: "다이어트 없이 운동 없이 허벅지 얇아지는 법"
  * 학교상황: "우리반에서 갑자기 예뻐진 애 이유"
  * 충격: "다들 이정도 블랙헤드는 가지고있지?"
- 첫 3줄 안에 제품명/광고 느낌 절대 금지
- 바로 자기 얘기로 전환: "나도 진짜 ~였거든"
- image_slot: "hooking"

### 장면3-A: 스토리 전반 - 계기와 감정 (type: "text") - 6~8줄
[감정: 공감 → 불안 → 걱정]

(1) 구체적 계기 (2~3줄):
  - 반드시 "시간+장소+상황": "작년 여름에 친구랑 수영장 갔는데"
  - 타인의 말 직접 인용: "걔가 그러는데 ~래", "엄마가 ~라고 했거든"
  - "어느날" 같은 막연한 표현 금지

(2) 감정 변화 (2~3줄):
  - 감정을 행동으로: "거울 볼때마다 한숨", "셀카 확대해서 모공 확인"
  - "신경쓰이다"(X) → "화장실 갈때마다 거울 들여다봄"(O)

(3) 사회적 압박 (2줄):
  - "인스타 보면 다들 피부 좋은데 나만...", "단체사진에서 내 얼굴만 칙칙"

### 장면3-B: 스토리 후반 - 시도와 좌절 (type: "text") - 6~8줄
[감정: 걱정 → 절박 → 좌절 → 포기 직전]
★ 대본에서 가장 중요한 "감정의 바닥". 여기서 충분히 좌절해야 솔루션 가치가 올라감.

(4) 시도와 실패 (4~5줄):
  - 최소 3가지 시도. 각각 "뭘 했고 + 왜 안됐는지" 한 세트:
  - "코팩 3일 연속 붙여봤는데 다음날 또 올라옴"
  - "다이소에서 ~사서 써봤는데 그때뿐"
  - "병원 알아봤는데 가격 보고 바로 포기ㅋㅋ"
  - 돈/기간 구체적으로: "몇만원 날림", "2주 써봤는데 변화없음"

(5) 전환점 (2~3줄):
  - 반드시 "우연히/어쩌다" 느낌: "포기하고 있었는데 인스타에서 우연히 봄"
  - 의도적으로 찾은 느낌 나면 광고처럼 보임

### 장면4: 원인/정보 (type: "text") - 5~7줄
[감정: 좌절 → 납득 "아 이래서 그랬구나"]
- 지금까지 왜 안 됐는지 원인 설명
- 전문적이지만 친구한테 설명하듯: "알고보니 ~거든?"
- 핵심 원인 키워드 **볼드** 처리
- 병원/전문시술 한계 언급 → 제품 가치 상승

### 장면5: 솔루션 (type: "image_text") - 5~7줄
[감정: 납득 → 기대]
- "그래서 내가 찾은 게 ~인데"로 자연스럽게 연결
- 원인→솔루션 논리적 연결 필수
- 차별점 1~2줄
- 광고 느낌 절대 금지. "친구가 알려줘서 써봤는데" 톤
- image_slot: "product"

### 장면6: 사용 후기/증거 (type: "image_text") - 5~7줄
[감정: 기대 → 확신]
- 시간순 변화 필수: "처음엔 반신반의" → "1주일쯤 약간?" → "한달 지나니까 확실히"
- 구체적 변화: 색상, 질감, 크기, 느낌
- 또래 반응: "같은반 애가 뭐 했냐고 물어봄", "셀카 올렸더니 댓글 폭발"
- image_slot: "before_after"

### 장면7: 추가 팁 (type: "text") - 3~4줄
[감정: 확신 유지]
- "참고로~", "그리고 ~하면 더 좋아"
- 사용법 팁, 비교 정보

### 장면8: 마무리 (type: "text") - 3~4줄
[감정: 확신 → 행동]
- 구체적 대상: "나처럼 ~고민하는 사람들"
- 가벼운 마무리: "진짜 한번 써봐", "후회 안 할거야"
- "구매/링크/할인/이벤트/한정" 단어 자체를 쓰지 마
- "링크 남겨둘게" 같은 표현도 금지
- 간접 유도만: "궁금한 사람?", "댓글로 알려줄게", "프로필에 있음"

## 감정 곡선
호기심(100%) → 공감(80%) → 불안(60%) → 절박(40%) → 좌절(20%) → 납득(50%) → 기대(75%) → 확신(95%) → 행동

## 리얼함 5원칙
1. 시공간: "작년 여름에", "체육시간에" - "어느날" 금지
2. 타인 목소리: "걔가 ~래", "엄마가 ~라고" - 직접 인용
3. 무관 디테일: "근데 그날 비 왔었거든" - 진실성 높이는 불필요 정보
4. 실패 구체성: "~크림 2주 써봤는데 포기" - 기간+결과+이유
5. 감정 행동화: "속상했다"(X) → "이불 속에서 혼자 울었음ㅋㅋ"(O)

## 말투
- 같은 반 친구가 카톡으로 추천하는 반말체
- ㅋㅋ, ㅜㅜ는 3줄에 1번 이하
- 어미 다양하게: ~더라고, ~있지?, ~거든, ~는데, ~ㅋㅋ, ~임, ~거야, ~잖아
- "진짜", "약간", "은근", "걍", "되게" 자연스럽게
- 같은 어미 3줄 연속 금지
- "추천드립니다", "소개해드릴게요" 같은 어른 말투 금지

## 절대 금지
- 광고 문구 ("놀라운 효과!", "지금 바로!")
- 스토리 없이 바로 제품 소개
- 스토리 10줄 이하 (최소 12줄)
- 시도/실패 2개 이하 (최소 3가지)
- 비현실적 효과 ("하루만에 달라짐")
- "링크", "구매", "할인" 같은 직접 CTA

## 볼드
핵심 키워드 **볼드** (한 줄에 1~2개만)

## 출력 (반드시 JSON)
```json
{
  "title": "영상 제목",
  "thumbnail_title": "네이트판 스타일 제목",
  "scenes": [
    {"type":"thumbnail","title":"네이트판 제목","category":"19","duration":2.5},
    {"type":"image_text","name":"hooking","image_slot":"hooking","lines":["줄1","줄2"]},
    {"type":"text","name":"story_emotion","lines":["스토리 전반"]},
    {"type":"text","name":"story_struggle","lines":["스토리 후반"]},
    {"type":"text","name":"information","lines":["원인/정보"]},
    {"type":"image_text","name":"solution","image_slot":"product","lines":["솔루션"]},
    {"type":"image_text","name":"proof","image_slot":"before_after","lines":["후기"]},
    {"type":"text","name":"tips","lines":["추가 팁"]},
    {"type":"text","name":"closing","lines":["마무리"]}
  ]
}
```
JSON만 출력해. 다른 설명 없이."""


IMAGE_SLOT_NAMES = {"hooking", "product", "before_after"}


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
            "category": "19",
            "duration": 2.5,
        })

    for s in raw_scenes:
        if s.get("type") == "thumbnail":
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

        # 긴 스토리를 전반/후반으로 자동 분리
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

    if not topic:
        return json_response({"error": "주제를 입력해주세요"}, 400)

    try:
        client = get_client()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"주제/제품: {topic}\n설명: {description}",
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
