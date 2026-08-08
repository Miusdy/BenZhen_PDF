from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from PIL import Image
from pytesseract import Output

from .errors import OcrUnavailableError
from .image_preprocessing import preprocess_for_ocr


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float


class TesseractOcrEngine:
    def __init__(self, language: str) -> None:
        self.language = language
        self.command, self.tessdata_dir = self._locate_runtime()
        if self.command:
            pytesseract.pytesseract.tesseract_cmd = str(self.command)

    @staticmethod
    def _locate_runtime() -> tuple[Path | None, Path | None]:
        executable = shutil.which("tesseract")
        if executable:
            return Path(executable), None

        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        executable_root = Path(sys.executable).resolve().parent
        candidates = [
            bundle_root / "tesseract" / "bin" / "tesseract",
            bundle_root / "tesseract" / "tesseract",
            bundle_root / "tesseract" / "bin" / "tesseract.exe",
            bundle_root / "tesseract" / "tesseract.exe",
            executable_root / ".." / "Resources" / "resources" / "tesseract" / "bin" / "tesseract",
        ]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file():
                tessdata = resolved.parent.parent / "tessdata"
                return resolved, tessdata if tessdata.is_dir() else None
        return None, None

    def _config(self) -> str:
        if self.tessdata_dir:
            return f'--tessdata-dir "{self.tessdata_dir}"'
        return ""

    def available(self) -> bool:
        return self.command is not None

    def installed_languages(self) -> set[str]:
        if not self.available():
            return set()
        try:
            return set(pytesseract.get_languages(config=self._config()))
        except pytesseract.TesseractError:
            return set()

    def diagnose(self) -> list[str]:
        if not self.available():
            return ["未检测到 Tesseract OCR 程序"]
        required = set(self.language.split("+"))
        missing = required - self.installed_languages()
        return ["缺少 OCR 语言模型：" + ", ".join(sorted(missing))] if missing else []

    def recognize(self, image: Image.Image | Path) -> OcrResult:
        problems = self.diagnose()
        if problems:
            raise OcrUnavailableError("；".join(problems))
        source = Image.open(image) if isinstance(image, Path) else image
        processed = preprocess_for_ocr(source)
        data = pytesseract.image_to_data(
            processed,
            lang=self.language,
            output_type=Output.DICT,
            config=("--psm 3 " + self._config()).strip(),
        )
        words: list[str] = []
        confidences: list[float] = []
        last_line: tuple[int, int, int] | None = None
        for index, value in enumerate(data["text"]):
            word = value.strip()
            if not word:
                continue
            line = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
            if last_line is not None and line != last_line:
                words.append("\n")
            elif words and words[-1] != "\n":
                words.append(" ")
            words.append(word)
            last_line = line
            try:
                confidence = float(data["conf"][index])
                if confidence >= 0:
                    confidences.append(confidence / 100.0)
            except (TypeError, ValueError):
                continue
        score = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult("".join(words).strip(), round(score, 4))
