"""Generate the ExamChaiTer application icon."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "ExamChaiTer.ico"
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def main() -> None:
    image = Image.new("RGB", (256, 256), (28, 94, 156))
    draw = ImageDraw.Draw(image)
    font = _load_font(112)
    text = "EC"
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    position = ((256 - (right - left)) / 2, (256 - (bottom - top)) / 2 - top)
    draw.text(position, text, fill="white", font=font)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_PATH, format="ICO", sizes=[(256, 256)])


if __name__ == "__main__":
    main()
