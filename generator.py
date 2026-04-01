import json
import os
import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent

WIDTH, HEIGHT = 720, 1280
BG_COLOR = "#F0F0F0"
LINE_DURATION = 1.1

# 사용 가능한 폰트 목록
FONTS = {
    "malgun": {"name": "맑은 고딕", "path": "C:/Windows/Fonts/malgun.ttf", "bold": "C:/Windows/Fonts/malgunbd.ttf"},
    "gothic": {"name": "고딕", "path": "C:/Windows/Fonts/GOTHIC.TTF", "bold": "C:/Windows/Fonts/GOTHICB.TTF"},
    "gulim": {"name": "굴림", "path": "C:/Windows/Fonts/gulim.ttc", "bold": "C:/Windows/Fonts/gulim.ttc"},
    "jejugothic": {"name": "제주고딕", "path": "C:/Windows/Fonts/JejuGothic.ttf", "bold": "C:/Windows/Fonts/JejuGothic.ttf"},
}

# 추가 폰트 탐색
for name, info in [
    ("nanumgothic", {"name": "나눔고딕", "path": "C:/Windows/Fonts/NanumGothic.ttf", "bold": "C:/Windows/Fonts/NanumGothicBold.ttf"}),
    ("nanumbarungothic", {"name": "나눔바른고딕", "path": "C:/Windows/Fonts/NanumBarunGothic.ttf", "bold": "C:/Windows/Fonts/NanumBarunGothicBold.ttf"}),
    ("kopub", {"name": "KoPub돋움", "path": "C:/Windows/Fonts/KoPubDotumMedium.ttf", "bold": "C:/Windows/Fonts/KoPubDotumBold.ttf"}),
    ("notosanskr", {"name": "Noto Sans KR", "path": "C:/Windows/Fonts/NotoSansKR-Regular.ttf", "bold": "C:/Windows/Fonts/NotoSansKR-Bold.ttf"}),
]:
    if os.path.exists(info["path"]):
        FONTS[name] = info

DEFAULT_FONT = "malgun"


def get_font(size, bold=False, font_key=None):
    font_key = font_key or DEFAULT_FONT
    info = FONTS.get(font_key, FONTS[DEFAULT_FONT])
    path = info["bold"] if bold else info["path"]
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(FONTS[DEFAULT_FONT]["path"], size)


def get_available_fonts():
    return {k: v["name"] for k, v in FONTS.items()}


def create_simple_thumbnail(title, output_path):
    """심플 썸네일 - 사용자가 이미지 안 올렸을 때 제목만 표시"""
    img = Image.new("RGB", (WIDTH, HEIGHT), "#1A1A1A")
    draw = ImageDraw.Draw(img)

    title_font = get_font(38, bold=True)

    # 제목 줄바꿈 (15자 단위)
    lines = []
    while title:
        if len(title) <= 15:
            lines.append(title)
            break
        idx = title[:15].rfind(" ")
        if idx == -1:
            idx = 15
        lines.append(title[:idx].strip())
        title = title[idx:].strip()

    total_height = len(lines) * 56
    y = (HEIGHT - total_height) // 2

    for line in lines:
        bbox = title_font.getbbox(line)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        draw.text((x, y), line, fill="#FFFFFF", font=title_font)
        y += 56

    img.save(output_path, quality=95)
    return img


def create_natepann_thumbnail(title, output_path, category="19"):
    """네이트판 스타일 썸네일 생성"""
    img = Image.new("RGB", (WIDTH, HEIGHT), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (WIDTH, 80)], fill="#2B2B2B")
    top_font = get_font(22)
    draw.text((20, 28), "PANN", fill="#FFFFFF", font=top_font)

    rank_font = get_font(18)
    btn_y = 120
    draw.rounded_rectangle([(30, btn_y), (230, btn_y + 36)], radius=18, fill="#E8F5E9", outline="#4CAF50")
    draw.text((50, btn_y + 6), "+실시간 랭킹 더보기", fill="#4CAF50", font=rank_font)

    title_font = get_font(32, bold=True)
    title_y = 190
    draw.text((40, title_y), f"{category})) {title}", fill="#333333", font=title_font)

    info_font = get_font(16)
    info_y = title_y + 60
    draw.text((40, info_y), "23.12.19 17:58", fill="#999999", font=info_font)
    draw.text((40, info_y + 25), "추천 166", fill="#999999", font=info_font)

    comment_y = HEIGHT - 100
    draw.rectangle([(0, comment_y), (WIDTH, HEIGHT)], fill="#F5F5F5")
    draw.line([(0, comment_y), (WIDTH, comment_y)], fill="#E0E0E0", width=1)
    comment_font = get_font(20)
    draw.text((40, comment_y + 20), "댓글", fill="#333333", font=comment_font)
    draw.text((100, comment_y + 20), "116", fill="#FF3B30", font=get_font(20, bold=True))
    draw.text((WIDTH - 120, comment_y + 20), "댓글쓰기", fill="#999999", font=comment_font)
    draw.text((30, title_y - 50), "♣", fill="#FF3B30", font=get_font(40))

    img.save(output_path, quality=95)
    return img


def render_line_on_image(draw, line_text, y, style=None):
    """한 줄을 스타일에 맞게 렌더링하고 실제 그려진 높이를 반환"""
    import re
    style = style or {}

    font_size = style.get("fontSize", 32)
    font_color = style.get("color", "#1A1A1A")
    font_key = style.get("font", DEFAULT_FONT)
    align = style.get("align", "center")
    bold_color = style.get("boldColor", "#000000")

    font = get_font(font_size, False, font_key)
    font_bold = get_font(int(font_size * 1.1), True, font_key)

    # 볼드 파싱
    parts = re.split(r"(\*\*.*?\*\*)", line_text)
    segments = []
    total_width = 0
    for part in parts:
        is_bold = part.startswith("**") and part.endswith("**")
        clean = part.strip("*") if is_bold else part
        if not clean:
            continue
        f = font_bold if is_bold else font
        bbox = f.getbbox(clean)
        w = bbox[2] - bbox[0]
        segments.append({"text": clean, "bold": is_bold, "width": w, "font": f})
        total_width += w

    # 정렬
    if align == "center":
        x = (WIDTH - total_width) // 2
    elif align == "right":
        x = WIDTH - total_width - 50
    else:  # left
        x = 50

    for seg in segments:
        color = bold_color if seg["bold"] else font_color
        draw.text((x, y), seg["text"], fill=color, font=seg["font"])
        x += seg["width"]

    return font_size + 16  # 줄 높이 반환


def create_accumulate_frame(lines_data, current_index, base_image_path=None, output_path=None):
    """
    누적 프레임 생성.
    lines_data: [{"text": "...", "style": {...}, "image_path": "..."}, ...]
    current_index: 현재까지 보여줄 줄 인덱스 (0-based, inclusive)
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 장면 기본 이미지
    text_start_y = 60
    if base_image_path and os.path.exists(base_image_path):
        ref_img = Image.open(base_image_path)
        img_area_height = int(HEIGHT * 0.35)
        ref_img.thumbnail((WIDTH - 80, img_area_height), Image.Resampling.LANCZOS)
        x = (WIDTH - ref_img.width) // 2
        y = 30
        img.paste(ref_img, (x, y))
        text_start_y = y + ref_img.height + 20

    y = text_start_y

    for i in range(current_index + 1):
        line = lines_data[i]
        line_text = line.get("text", "")
        style = line.get("style", {})
        line_image = line.get("image_path", "")

        # 줄에 이미지가 있으면 삽입
        if line_image and os.path.exists(line_image):
            li = Image.open(line_image)
            max_h = int(HEIGHT * 0.25)
            li.thumbnail((WIDTH - 100, max_h), Image.Resampling.LANCZOS)
            lx = (WIDTH - li.width) // 2
            img.paste(li, (lx, y))
            y += li.height + 12
            # 이미지만 있는 줄이면 텍스트 스킵
            if not line_text.strip():
                continue

        if line_text.strip():
            line_h = render_line_on_image(draw, line_text, y, style)
            y += line_h

    if output_path:
        img.save(output_path, quality=95)
    return img


def generate_video(scenes, output_dir=None):
    """장면 리스트로부터 최종 영상 생성"""
    if output_dir is None:
        output_dir = BASE_DIR / "output"
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    video_id = uuid.uuid4().hex[:8]
    temp_dir = output_dir / f"temp_{video_id}"
    temp_dir.mkdir(exist_ok=True)

    frame_files = []
    durations = []
    frame_idx = 0

    for scene in scenes:
        scene_type = scene.get("type", "text")

        if scene_type == "thumbnail":
            frame_path = temp_dir / f"frame_{frame_idx:04d}.png"
            image_path = scene.get("image_path", "")
            if image_path and os.path.exists(image_path):
                thumb = Image.open(image_path)
                thumb = thumb.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                thumb.save(str(frame_path), quality=95)
            else:
                # 이미지 없으면 제목 텍스트만 심플하게 표시
                create_simple_thumbnail(
                    title=scene.get("title", "제목"),
                    output_path=str(frame_path),
                )
            frame_files.append(frame_path)
            durations.append(scene.get("duration", 2.5))
            frame_idx += 1

        else:
            lines_data = scene.get("lines_data", [])
            # 하위 호환: lines만 있는 경우 변환
            if not lines_data and scene.get("lines"):
                lines_data = [{"text": l, "style": {}} for l in scene["lines"]]

            base_image = scene.get("image_path", "")

            for li in range(len(lines_data)):
                frame_path = temp_dir / f"frame_{frame_idx:04d}.png"
                create_accumulate_frame(
                    lines_data, li,
                    base_image_path=base_image,
                    output_path=str(frame_path),
                )
                frame_files.append(frame_path)
                dur = lines_data[li].get("duration", LINE_DURATION)
                durations.append(dur)
                frame_idx += 1

            # 마지막 줄 살짝 더 유지
            if durations:
                durations[-1] += 0.5

    if not frame_files:
        raise ValueError("생성할 프레임이 없습니다")

    # ffmpeg concat
    concat_path = temp_dir / "concat.txt"
    with open(concat_path, "w", encoding="utf-8") as f:
        for fp, dur in zip(frame_files, durations):
            f.write(f"file '{fp.as_posix()}'\n")
            f.write(f"duration {dur}\n")
        f.write(f"file '{frame_files[-1].as_posix()}'\n")

    output_path = output_dir / f"tiktok_{video_id}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_path),
        "-vf", f"scale={WIDTH}:{HEIGHT},format=yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-r", "30",
    ]

    bgm_dir = BASE_DIR / "static" / "bgm"
    bgm_files = list(bgm_dir.glob("*.mp3"))
    if bgm_files:
        total_dur = sum(durations)
        fade_start = max(0, total_dur - 2)
        cmd.extend(["-i", str(bgm_files[0]), "-c:a", "aac", "-b:a", "128k",
                     "-shortest", "-af", f"afade=t=out:st={fade_start}:d=2"])
    else:
        cmd.extend(["-an"])

    cmd.append(str(output_path))
    subprocess.run(cmd, capture_output=True, text=True)

    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    return str(output_path)
