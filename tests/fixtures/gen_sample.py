"""Generate the synthetic OCR fixture without using real exam content."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_PATH = Path(__file__).with_name("synthetic_question.png")
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simsun.ttc"),
)
LINES = ("第一行 题目示例", "Second line sample", "12345")


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    raise FileNotFoundError("No CJK-capable Windows font found")


def main() -> None:
    image = Image.new("RGB", (720, 260), "white")
    draw = ImageDraw.Draw(image)
    font = _load_font(44)

    for index, line in enumerate(LINES):
        draw.text((40, 30 + index * 75), line, fill="black", font=font)

    image.save(OUTPUT_PATH)


if __name__ == "__main__":
    main()
