import shutil

import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output

from documind_ai.schemas import BoundingBox, PageText, WordToken


def recognize(image: Image.Image, number: int, width: float, height: float) -> PageText:
    if not shutil.which("tesseract"):
        raise RuntimeError(
            "Tesseract is unavailable. Use the supplied Docker image or install Tesseract."
        )
    if image.width * image.height > 30_000_000:
        raise RuntimeError("Image exceeds the OCR pixel limit")
    prepared = ImageOps.grayscale(image)
    # Orientation detection is best-effort. Low-text pages often cannot be oriented reliably.
    try:
        orientation = pytesseract.image_to_osd(prepared, output_type=Output.DICT, timeout=15)
        rotation = orientation.get("rotate", 0)
    except (pytesseract.TesseractError, RuntimeError):
        rotation = 0
    # Preserve the page coordinate system: rotate tokens back when processing rotated images.
    oriented = prepared.rotate(-rotation, expand=True) if rotation else prepared
    data = pytesseract.image_to_data(oriented, lang="eng", output_type=Output.DICT, timeout=45)
    tokens = []
    lines: dict[tuple[int, int, int], list[str]] = {}
    for index, text in enumerate(data["text"]):
        if not text.strip() or float(data["conf"][index]) < 0:
            continue
        left, top = data["left"][index], data["top"][index]
        right, bottom = left + data["width"][index], top + data["height"][index]
        corners = [(left, top), (right, top), (left, bottom), (right, bottom)]
        if rotation == 90:
            corners = [(y, prepared.height - x) for x, y in corners]
        elif rotation == 180:
            corners = [(prepared.width - x, prepared.height - y) for x, y in corners]
        elif rotation == 270:
            corners = [(prepared.width - y, x) for x, y in corners]
        xs, ys = zip(*corners, strict=True)
        tokens.append(
            WordToken(
                token_id=len(tokens) + 1,
                text=text.strip(),
                line_id=f"{data['block_num'][index]}-{data['par_num'][index]}-{data['line_num'][index]}",
                box=BoundingBox(
                    x0=min(xs) * width / prepared.width,
                    top=min(ys) * height / prepared.height,
                    x1=max(xs) * width / prepared.width,
                    bottom=max(ys) * height / prepared.height,
                ),
            )
        )
        key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        lines.setdefault(key, []).append(text.strip())
    return PageText(
        page_number=number,
        width=width,
        height=height,
        rotation=rotation,
        status="ocr_text" if tokens else "ocr_failed",
        extraction_method="ocr",
        text="\n".join(" ".join(line) for line in lines.values()),
        tokens=tokens,
        image_count=1,
    )
