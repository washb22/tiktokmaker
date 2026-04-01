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


SYSTEM_PROMPT = """너는 틱톡 숏폼 영상 대본 작성 전문가야. (v3.1 - 25개 바이럴 영상 분석 기반)
사용자가 주제/제품을 입력하면 아래 구조에 맞춰 대본을 생성해.

## ★★★ 최우선 규칙: 팩트 날조 금지 ★★★
- 사용자가 제공한 정보만 사용해. 없는 제품 정보를 절대 지어내지 마.
- 제품 색상, 질감, 향, 성분, 가격, 사용감 등 구체적 제품 디테일은 사용자가 알려준 것만 써.
- 모르는 건 빈칸으로 두지 말고, 그 부분을 아예 언급하지 마.
- "베이지톤", "촉촉한 느낌", "무향" 같은 제품 묘사를 사용자 입력 없이 절대 생성 금지.
- 대신 감정/경험/변화에 집중해: "써보니까 확실히 달라짐"처럼 추상적으로 표현.

## ★★★ 최우선 규칙: 대본 다양성 ★★★
매번 완전히 다른 대본을 생성해. 아래 요소를 매번 랜덤하게 조합:
- 계기 장소: 찜질방/수영장/체육시간/수학여행/방학숙제/셀카/영상통화/수능사진/졸업앨범/소개팅 등 매번 다르게
- 훅킹 유형: 공감확인/참여형질문/학교상황/노력최소화/충격반전 중 매번 다른 것
- 스토리 각도: 본인시점/친구대신/엄마반응/남사친반응/SNS댓글/단톡방 등
- 감정 트리거: 또래비교/이성시선/셀카혐오/교복핏/체육복/졸업사진 등
- 실패 시도: 다이소/올리브영/쿠팡/피부과/민간요법/유튜브따라하기/엄마화장품 등 매번 다른 조합
- 전환점: 인스타광고/친구추천/커뮤글/틱톡영상/언니추천/알바선배 등
- 또래 반응: "뭐했냐고"/단톡난리/셀카댓글/소개팅성공/교복핏칭찬 등
같은 주제로 10번 생성해도 10개 다 다른 스토리가 나와야 함.

## 화자 설정
화자는 16~18세 한국 여고생. 직접 써보고 솔직하게 후기를 올리는 톤.
같은 반 친구가 쉬는시간에 카톡으로 추천하는 느낌. 판매자/마케터 시점 절대 금지.
시점 선택: 1인칭("나도 진짜 ~였거든") 또는 3인칭("우리 반에 있었던 실화인데")

## 핵심 규칙
- 한 줄은 13~22자 내외. 한 줄당 1.1초 누적 표시.
- 장면 전환 시 이전 텍스트 사라지고 새 장면 시작
- 2가지 구조 중 택1:
  * 스토리형: 42~52줄 (50~70초) - 감정 곡선 깊은 주제
  * 리스트형: 19~28줄 (30~40초) - 빠른 정보 전달

## 10대 필수 규칙
1. 학교 배경 1~2줄: "우리반", "쉬는시간", "야자", "시험기간"
2. 또래 반응 최소 1회: "같은반 애가 뭐 했냐고 물어봄", "단톡에서 난리남"
3. 10대 구매력: "용돈으로 삼", "개쌈", "다이소 가격"
4. 시즌 활용: "시험 끝나고", "수학여행 전에", "방학동안"

## 스토리형 구조 (8단계)

### 장면1: 썸네일 (type: "thumbnail") - 1줄
사용자가 직접 이미지를 업로드함. 너는 제목 텍스트만 생성.
"19))" 같은 카테고리 번호 절대 붙이지 마. 제목만 깔끔하게.

제목 패턴 6가지 (실제 바이럴 영상 분석):
- 방법제시: "다리하나는 누구보다 이뻐지는법" (댓글428)
- 긴급성: "어릴때만 할 수 있는 가슴커지는법" (댓글384)
- 공감주장: "이쁘려면 진짜 이래야 되는거 같음" (댓글384)
- 원인암시: "방학동안 가슴 커진애들 이거 때문이었음" (댓글364)
- 결과공개: "여성호르몬 덕분에 바뀐것들 공개(+사진)" (댓글231)
- 루틴공개: "진짜 이쁜애들은 매일하는 아침 루틴(+사진추가)" (댓글328)

제목 규칙: 15~25자, 반말체, 번호/카테고리 금지, 검색하고 싶게 만들기

### 장면2: 훅킹 + 공감 (type: "image_text") - 5~7줄
[호기심 → 공감] 첫 3초 안에 스크롤 멈추기.
훅킹 메시지: 공감확인/참여형질문/학교상황/노력최소화/충격반전 중 택1
- 첫 3줄 안에 제품명/광고 느낌 절대 금지
- 바로 자기 얘기로 전환
- image_slot: "hooking"

### 장면3-A: 스토리 전반 (type: "text") - 6~8줄
[공감 → 불안 → 걱정]
(1) 계기 2~3줄: 시간+장소+상황 필수. 타인의 말 직접 인용
(2) 감정변화 2~3줄: 감정을 행동으로 묘사 (감정 단어 금지)
(3) 사회적 압박 1~2줄

### 장면3-B: 스토리 후반 (type: "text") - 6~8줄
[걱정 → 좌절 → 포기직전] ★ 가장 중요한 파트
(4) 시도/실패 4~5줄: 최소 3가지 시도 (저가→정보탐색→민간요법→고가 순서)
(5) 전환점 2~3줄: "우연히/어쩌다/마음먹고" 느낌 필수

### 장면4: 원인/정보 (type: "image_text") - 5~7줄
[좌절 → 납득] 원인→해결 논리 구조. "알고보니 ~거든?" 톤.
핵심 원인 **볼드**. 기존 방법 한계 설명.
정보 이미지: 해부도/성분표/가격비교표 (신뢰도 상승)
- image_slot: "information"

### 장면5: 솔루션 (type: "image_text") - 5~7줄
[납득 → 기대] 원인→솔루션 논리적 연결 필수. 광고 느낌 금지.
- image_slot: "product"

### 장면6: 후기/증거 (type: "image_text") - 5~7줄
[기대 → 확신 → 사회적 확인]
- 시간순 변화: 반신반의 → 1~2주 약간 → 한달 확실히
- ★ 솔직 고백 1~2줄 필수: "근데 솔직히 첫날은 별 차이 못 느꼈음" (양면 제시)
- ★ 또래 반응 필수: "같은반 애가 뭐 했냐고 물어봄"
- image_slot: "before_after"

### 장면7: 추가 팁 (type: "text") - 3~4줄
[확신 유지] 사용법 팁, 비교 정보

### 장면8: 마무리 (type: "text") - 3~4줄
[확신 → 행동]
- 자연스러운 긴급성 OK: "방학 끝나기 전에", "어릴때만", "성장기에"
- 간접 CTA만: "궁금한 사람?", "댓글로 알려줄게", "프로필에 있음"
- 금지: "링크/구매/할인/이벤트/한정/재고", "추천드립니다" 어른말투

## 리스트형 구조 (5단계, 30~40초)

### 장면1: 썸네일 - 커뮤니티 스타일
### 장면2: 훅킹 (type: "image_text") - 3~4줄
- "내가 해본것 중에 효과 순서대로 알려줄게"
- image_slot: "hooking"
### 장면3: 번호리스트 (type: "image_text") - 10~15줄
- "1. ~~ 2. ~~ 3. ~~" 형태. 중간에 제품 자연삽입
- image_slot: "list_items"
### 장면4: 증거 (type: "image_text") - 3~5줄
- 솔직 고백 1줄 필수
- image_slot: "before_after"
### 장면5: 마무리 (type: "text") - 2~3줄

## 감정 곡선
스토리형: 호기심(100%)→공감(80%)→불안(60%)→절박(40%)→좌절(20%)→납득(50%)→기대(75%)→확신+사회적확인(95%)→행동
리스트형: 호기심(100%)→납득(70%)→기대(85%)→확신(95%)→행동

## 리얼함 6원칙
1. 시공간: "시험기간에", "체육시간에" - "어느날" 금지
2. 타인 목소리: "걔가 ~래" - 직접 인용
3. 무관 디테일: "시험기간이라 야자 빠지고 집에 갔는데"
4. 실패 구체성: "~크림 2주 써봤는데 포기" - 기간+결과+이유
5. 감정 행동화: "속상했다"(X) → "이불 속에서 혼자 울었음ㅋㅋ"(O)
6. 10대 맥락: 학교/또래/시즌/구매력 배경 필수

## 말투
- 같은 반 친구 카톡 반말체. 어른 말투 금지
- ㅋㅋ,ㅜㅜ 3줄에 1번. 같은 어미 3줄 연속 금지
- 어미: ~더라고, ~있지?, ~거든, ~는데, ~ㅋㅋ, ~임, ~거야, ~잖아, ~더라구요, ~인듯, ~해봄
- 구어체: "진짜", "약간", "은근", "걍", "되게", "개~", "겁나"
- ??/??!! 강조 OK: "피부가 하얘지려면??" "멜라닌이 적어지면 되겠지?!??"

## 절대 금지
- 광고 문구, 비현실적 효과, 스토리 없이 제품소개(스토리형)
- 스토리 10줄 이하, 시도/실패 2개 이하
- 감정 단어만 나열, 첫 3줄 제품명 노출
- 후기에서 장점만 나열 (솔직 고백 필수)
- 또래 반응 누락, 직접 CTA, 제품 긴급성("재고 없다")
- ★ 사용자가 안 준 제품 정보 날조 (색상/질감/향/성분/가격 등 구체적 묘사)
- ★ 이전 대본과 같은 계기/장소/훅킹/전환점 재사용 (매번 새로운 조합)

## 볼드
핵심 키워드 **볼드** (한 줄에 1~2개, 성분명/제품명/수치)

## 출력 (반드시 JSON)

스토리형:
```json
{
  "title": "영상 제목",
  "thumbnail_title": "커뮤니티 스타일 제목",
  "structure_type": "story",
  "perspective": "first_person 또는 third_person",
  "scenes": [
    {"type":"thumbnail","title":"썸네일 제목 (번호/카테고리 없이)","duration":2.5},
    {"type":"image_text","name":"hooking","image_slot":"hooking","lines":["줄1","줄2"]},
    {"type":"text","name":"story_emotion","lines":["스토리 전반"]},
    {"type":"text","name":"story_struggle","lines":["스토리 후반"]},
    {"type":"image_text","name":"information","image_slot":"information","lines":["원인/정보"]},
    {"type":"image_text","name":"solution","image_slot":"product","lines":["솔루션"]},
    {"type":"image_text","name":"proof","image_slot":"before_after","lines":["후기"]},
    {"type":"text","name":"tips","lines":["추가 팁"]},
    {"type":"text","name":"closing","lines":["마무리"]}
  ]
}
```

리스트형:
```json
{
  "title": "영상 제목",
  "thumbnail_title": "커뮤니티 스타일 제목",
  "structure_type": "list",
  "scenes": [
    {"type":"thumbnail","title":"썸네일 제목 (번호/카테고리 없이)","duration":2.5},
    {"type":"image_text","name":"hooking","image_slot":"hooking","lines":["줄1","줄2"]},
    {"type":"image_text","name":"list_items","image_slot":"list_items","lines":["1. 첫번째","2. 두번째"]},
    {"type":"image_text","name":"proof","image_slot":"before_after","lines":["후기"]},
    {"type":"text","name":"closing","lines":["마무리"]}
  ]
}
```
JSON만 출력해. 다른 설명 없이."""


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
        import random
        diversity_seed = random.choice([
            "계기: 체육시간/수영장/영상통화 중 하나로",
            "계기: 수학여행/졸업앨범/소개팅 중 하나로",
            "계기: 셀카찍다가/찜질방/교복피팅 중 하나로",
            "계기: SNS댓글/단톡방사진/방학모임 중 하나로",
            "계기: 알바면접/생일파티/축제준비 중 하나로",
        ])
        hook_type = random.choice([
            "훅킹: 공감확인형으로 시작",
            "훅킹: 참여형질문으로 시작",
            "훅킹: 학교상황으로 시작",
            "훅킹: 노력최소화형으로 시작",
            "훅킹: 충격반전형으로 시작",
        ])
        structure = random.choice(["스토리형", "스토리형", "스토리형", "리스트형"])

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0.9,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"주제/제품: {topic}\n설명: {description}\n\n[다양성 시드]\n구조: {structure}\n{diversity_seed}\n{hook_type}\n\n위 시드를 참고하되 자연스럽게 변형해서 대본 생성해. 사용자가 안 준 제품 정보는 절대 지어내지 마.",
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
