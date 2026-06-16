from __future__ import annotations

import html
import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

try:
    import docx
except ImportError:  # pragma: no cover - surfaced at runtime
    docx = None


SUPPORTED_EXTENSIONS = {".docx", ".pptx"}
LEGACY_EXTENSIONS = {".doc", ".ppt"}

PML_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

DOCX_IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
PPTX_IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


@dataclass(frozen=True)
class ConversionResult:
    source_name: str
    package_name: str
    package_path: Path


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "course"


def convert_file_to_scorm(source_path: Path, output_dir: Path) -> ConversionResult:
    source_path = source_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        if suffix in LEGACY_EXTENSIONS:
            target_extension = ".docx" if suffix == ".doc" else ".pptx"
            raise ValueError(
                f"{source_path.name} is a legacy Office file. Save it as "
                f"{source_path.stem}{target_extension} first."
            )
        raise ValueError(f"{source_path.name} is not a supported .docx or .pptx file.")

    course_slug = slugify(source_path.stem)
    package_root = output_dir / f"{course_slug}_scorm"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    assets_dir = package_root / "assets"
    assets_dir.mkdir()

    if suffix == ".docx":
        title, body_html = docx_to_html(source_path, assets_dir)
    else:
        title, body_html = pptx_to_html(source_path, assets_dir)

    title = title or source_path.stem
    (package_root / "index.html").write_text(
        build_index_html(title=title, body_html=body_html),
        encoding="utf-8",
    )
    (package_root / "scorm_api.js").write_text(build_scorm_api_js(), encoding="utf-8")
    manifest_files = sorted(
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
    )
    (package_root / "imsmanifest.xml").write_text(
        build_manifest(
            title=title,
            identifier=f"BRX-{course_slug}-{uuid.uuid4().hex[:8]}",
            files=manifest_files,
        ),
        encoding="utf-8",
    )

    package_path = output_dir / f"{course_slug}_scorm.zip"
    if package_path.exists():
        package_path.unlink()
    zip_directory(package_root, package_path)

    return ConversionResult(
        source_name=source_path.name,
        package_name=package_path.name,
        package_path=package_path,
    )


def docx_to_html(source_path: Path, assets_dir: Path) -> tuple[str, str]:
    if docx is None:
        raise RuntimeError("python-docx is required for DOCX conversion.")

    document = docx.Document(str(source_path))
    title = source_path.stem
    parts: list[str] = []
    image_map = extract_docx_images(source_path, assets_dir)

    for block in iter_docx_blocks(document):
        if block.__class__.__name__ == "Paragraph":
            text = "".join(run.text for run in block.runs).strip()
            image_html = images_for_paragraph(block, image_map)
            if not text and not image_html:
                continue
            style_name = (block.style.name if block.style is not None else "").lower()
            if "title" in style_name and text:
                title = text
                parts.append(f"<h1>{html.escape(text)}</h1>")
            elif "heading 1" in style_name and text:
                parts.append(f"<h2>{html.escape(text)}</h2>")
            elif "heading 2" in style_name and text:
                parts.append(f"<h3>{html.escape(text)}</h3>")
            elif text:
                parts.append(f"<p>{html.escape(text)}</p>")
            parts.extend(image_html)
        elif block.__class__.__name__ == "Table":
            parts.append(table_to_html(block))

    if not parts:
        parts.append("<p>No readable text was found in this document.</p>")

    return title, "\n".join(parts)


def iter_docx_blocks(document) -> Iterable[object]:
    from docx.document import Document as DocxDocument
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if not isinstance(document, DocxDocument):
        raise TypeError("Expected a python-docx Document.")

    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def extract_docx_images(source_path: Path, assets_dir: Path) -> dict[str, str]:
    image_map: dict[str, str] = {}
    with zipfile.ZipFile(source_path) as archive:
        try:
            rels_xml = archive.read("word/_rels/document.xml.rels")
        except KeyError:
            return image_map
        root = ET.fromstring(rels_xml)
        for rel in root:
            if rel.attrib.get("Type") != DOCX_IMAGE_REL:
                continue
            rel_id = rel.attrib.get("Id")
            target = rel.attrib.get("Target", "")
            if not rel_id or not target:
                continue
            media_path = f"word/{target}" if not target.startswith("word/") else target
            if media_path not in archive.namelist():
                continue
            asset_name = f"docx-{slugify(Path(target).stem)}{Path(target).suffix}"
            asset_path = assets_dir / asset_name
            asset_path.write_bytes(archive.read(media_path))
            image_map[rel_id] = f"assets/{asset_name}"
    return image_map


def images_for_paragraph(paragraph, image_map: dict[str, str]) -> list[str]:
    image_html: list[str] = []
    for drawing in paragraph._element.findall(".//a:blip", PML_NS):
        rel_id = drawing.attrib.get(f"{{{PML_NS['r']}}}embed")
        if rel_id and rel_id in image_map:
            image_html.append(f'<figure><img src="{html.escape(image_map[rel_id])}" alt=""></figure>')
    return image_html


def table_to_html(table) -> str:
    rows = []
    for row in table.rows:
        cells = "".join(f"<td>{html.escape(cell.text.strip())}</td>" for cell in row.cells)
        rows.append(f"<tr>{cells}</tr>")
    return f"<table>{''.join(rows)}</table>"


def pptx_to_html(source_path: Path, assets_dir: Path) -> tuple[str, str]:
    slides: list[str] = []
    with zipfile.ZipFile(source_path) as archive:
        slide_names = sorted(
            [name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        for index, slide_name in enumerate(slide_names, start=1):
            slide_xml = ET.fromstring(archive.read(slide_name))
            text_blocks = extract_pptx_text_blocks(slide_xml)
            image_paths = extract_pptx_slide_images(archive, slide_name, index, assets_dir)
            slides.append(build_slide_html(index, text_blocks, image_paths))

    if not slides:
        slides.append('<section class="slide"><p>No readable slides were found.</p></section>')

    return source_path.stem, "\n".join(slides)


def extract_pptx_text_blocks(slide_xml: ET.Element) -> list[str]:
    blocks: list[str] = []
    for paragraph in slide_xml.findall(".//a:p", PML_NS):
        runs = [node.text or "" for node in paragraph.findall(".//a:t", PML_NS)]
        text = " ".join(piece.strip() for piece in runs if piece.strip()).strip()
        if text:
            blocks.append(text)
    return blocks


def extract_pptx_slide_images(
    archive: zipfile.ZipFile,
    slide_name: str,
    slide_number: int,
    assets_dir: Path,
) -> list[str]:
    rels_name = slide_name.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    if rels_name not in archive.namelist():
        return []

    rel_root = ET.fromstring(archive.read(rels_name))
    rel_targets: dict[str, str] = {}
    for rel in rel_root:
        if rel.attrib.get("Type") == PPTX_IMAGE_REL:
            rel_targets[rel.attrib.get("Id", "")] = rel.attrib.get("Target", "")

    slide_xml = ET.fromstring(archive.read(slide_name))
    image_paths: list[str] = []
    for position, blip in enumerate(slide_xml.findall(".//a:blip", PML_NS), start=1):
        rel_id = blip.attrib.get(f"{{{PML_NS['r']}}}embed")
        target = rel_targets.get(rel_id or "")
        if not target:
            continue
        media_path = normalize_pptx_relationship_target(slide_name, target)
        if media_path not in archive.namelist():
            continue
        suffix = Path(media_path).suffix or ".png"
        asset_name = f"slide-{slide_number}-image-{position}{suffix}"
        (assets_dir / asset_name).write_bytes(archive.read(media_path))
        image_paths.append(f"assets/{asset_name}")
    return image_paths


def normalize_pptx_relationship_target(slide_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    slide_dir = Path(slide_name).parent
    normalized = (slide_dir / target).as_posix()
    parts: list[str] = []
    for part in normalized.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def build_slide_html(index: int, text_blocks: list[str], image_paths: list[str]) -> str:
    content: list[str] = [f'<section class="slide" data-slide="{index}">']
    content.append(f'<div class="slide-number">Slide {index}</div>')
    if image_paths:
        content.append('<div class="slide-media">')
        for path in image_paths:
            content.append(f'<img src="{html.escape(path)}" alt="">')
        content.append("</div>")
    if text_blocks:
        content.append('<div class="slide-text">')
        for block_index, text in enumerate(text_blocks):
            tag = "h2" if block_index == 0 else "p"
            content.append(f"<{tag}>{html.escape(text)}</{tag}>")
        content.append("</div>")
    content.append("</section>")
    return "\n".join(content)


def build_index_html(title: str, body_html: str) -> str:
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <script src="scorm_api.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1e293b;
      --muted: #64748b;
      --line: #d8dee9;
      --accent: #0f766e;
      --paper: #ffffff;
      --canvas: #f4f7fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--canvas);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 64px;
      padding: 12px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
    }}
    header h1 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
    }}
    main {{
      width: min(1040px, calc(100% - 32px));
      margin: 28px auto;
      padding-bottom: 48px;
    }}
    article {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: clamp(20px, 4vw, 44px);
      box-shadow: 0 12px 40px rgba(30, 41, 59, 0.08);
    }}
    h1, h2, h3 {{ line-height: 1.2; }}
    p, li, td {{ font-size: 16px; line-height: 1.65; }}
    figure {{ margin: 24px 0; }}
    img {{ max-width: 100%; height: auto; border-radius: 6px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
    td {{ border: 1px solid var(--line); padding: 10px; vertical-align: top; }}
    button {{
      min-height: 40px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 0 14px;
      color: white;
      background: var(--accent);
      font-weight: 650;
      cursor: pointer;
    }}
    button:disabled {{ opacity: 0.55; cursor: not-allowed; }}
    .course-progress {{
      min-width: 180px;
      color: var(--muted);
      font-size: 14px;
      text-align: right;
    }}
    .slide {{
      min-height: min(680px, 75vh);
      display: none;
      align-content: start;
      gap: 20px;
    }}
    .slide.active {{ display: grid; }}
    .slide-number {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .slide-media {{
      display: grid;
      gap: 14px;
      justify-items: center;
    }}
    .slide-media img {{
      max-height: 440px;
      object-fit: contain;
      background: #f8fafc;
      border: 1px solid var(--line);
    }}
    .slide-text h2 {{ margin: 0 0 12px; font-size: clamp(26px, 4vw, 42px); }}
    .nav {{
      display: none;
      align-items: center;
      gap: 10px;
    }}
    body.has-slides .nav {{ display: flex; }}
    @media (max-width: 720px) {{
      header {{ align-items: start; flex-direction: column; }}
      .course-progress {{ text-align: left; }}
      main {{ width: min(100% - 20px, 1040px); margin-top: 12px; }}
      article {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{safe_title}</h1>
    <div class="nav" aria-label="Slide controls">
      <button type="button" id="prevBtn">Previous</button>
      <button type="button" id="nextBtn">Next</button>
      <span class="course-progress" id="courseProgress"></span>
    </div>
    <div class="course-progress" id="docProgress">Progress saved to LMS</div>
  </header>
  <main>
    <article id="content">
      {body_html}
    </article>
  </main>
  <script>
    const slides = Array.from(document.querySelectorAll('.slide'));
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const progress = document.getElementById('courseProgress');
    const docProgress = document.getElementById('docProgress');
    let currentSlide = 0;

    window.ScormRuntime.init();

    if (slides.length > 0) {{
      document.body.classList.add('has-slides');
      docProgress.hidden = true;
      showSlide(0);
    }} else {{
      window.ScormRuntime.setComplete();
    }}

    function showSlide(index) {{
      currentSlide = Math.max(0, Math.min(index, slides.length - 1));
      slides.forEach((slide, slideIndex) => slide.classList.toggle('active', slideIndex === currentSlide));
      prevBtn.disabled = currentSlide === 0;
      nextBtn.textContent = currentSlide === slides.length - 1 ? 'Finish' : 'Next';
      progress.textContent = `Slide ${{currentSlide + 1}} of ${{slides.length}}`;
      window.ScormRuntime.setProgress(Math.round(((currentSlide + 1) / slides.length) * 100));
      if (currentSlide === slides.length - 1) {{
        window.ScormRuntime.setComplete();
      }}
    }}

    prevBtn?.addEventListener('click', () => showSlide(currentSlide - 1));
    nextBtn?.addEventListener('click', () => {{
      if (currentSlide === slides.length - 1) {{
        window.ScormRuntime.setComplete();
        window.ScormRuntime.finish();
      }} else {{
        showSlide(currentSlide + 1);
      }}
    }});
    window.addEventListener('beforeunload', () => window.ScormRuntime.finish());
  </script>
</body>
</html>
"""


def build_scorm_api_js() -> str:
    return r"""(function () {
  function findApi(win) {
    let attempts = 0;
    while (win && attempts < 8) {
      if (win.API) return win.API;
      attempts += 1;
      win = win.parent && win.parent !== win ? win.parent : win.opener;
    }
    return null;
  }

  const api = findApi(window);
  let initialized = false;
  let finished = false;

  function call(method, ...args) {
    if (!api || typeof api[method] !== "function") return "";
    try {
      return api[method](...args);
    } catch (error) {
      console.warn("SCORM call failed", method, error);
      return "";
    }
  }

  window.ScormRuntime = {
    init() {
      if (initialized) return;
      call("LMSInitialize", "");
      initialized = true;
      call("LMSSetValue", "cmi.core.lesson_status", "incomplete");
      call("LMSCommit", "");
    },
    setProgress(percent) {
      this.init();
      call("LMSSetValue", "cmi.core.score.raw", String(percent));
      call("LMSCommit", "");
    },
    setComplete() {
      this.init();
      call("LMSSetValue", "cmi.core.lesson_status", "completed");
      call("LMSSetValue", "cmi.core.score.raw", "100");
      call("LMSCommit", "");
    },
    finish() {
      if (!initialized || finished) return;
      call("LMSCommit", "");
      call("LMSFinish", "");
      finished = true;
    }
  };
})();"""


def build_manifest(title: str, identifier: str, files: list[str]) -> str:
    safe_title = html.escape(title)
    generated = datetime.now(timezone.utc).isoformat()
    file_nodes = "\n".join(f'      <file href="{html.escape(path)}" />' for path in files)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{identifier}" version="1.0"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                      http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
    <brx:generated xmlns:brx="https://beyondrisx.local/scorm">{generated}</brx:generated>
  </metadata>
  <organizations default="ORG-1">
    <organization identifier="ORG-1">
      <title>{safe_title}</title>
      <item identifier="ITEM-1" identifierref="RES-1">
        <title>{safe_title}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES-1" type="webcontent" adlcp:scormtype="sco" href="index.html">
{file_nodes}
    </resource>
  </resources>
</manifest>
"""


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())
