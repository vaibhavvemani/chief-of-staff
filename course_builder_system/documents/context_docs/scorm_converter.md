# SCORM Converter

Converts `.pptx` and `.docx` files into self-contained **SCORM 1.2** packages
(`.zip`) ready for upload to any SCORM-compliant LMS (Moodle, Cornerstone,
Blackboard, SCORM Cloud, Graphy, etc.).

## How it works

1. **LibreOffice headless** converts the source file to a pixel-perfect PDF.
2. **poppler `pdftoppm`** rasterizes each PDF page into a JPEG image
   (`slide-001.jpg`, `slide-002.jpg`, …) at 150 DPI / JPEG quality 85.
3. The images are wrapped in a SCORM 1.2 package containing:
   - `imsmanifest.xml` at the archive root (SCORM requirement).
   - `index.html` — slide-by-slide image viewer with Prev/Next buttons, arrow-key
     navigation, a "Slide X / N" counter, and SCORM completion tracking.
   - `scorm_api.js` — SCORM 1.2 API discovery + wrapper (classic script, no modules).
   - `slide-001.jpg … slide-NNN.jpg` — rasterized slides.
   - SCORM 1.2 XSD schemas bundled alongside the manifest.

No PDF.js, no ES modules, no web workers — every asset is a plain `.jpg` or
`.js` file that any LMS content host serves correctly regardless of MIME config.

## Prerequisites

- **Python 3.8+** (stdlib only — no pip installs needed)
- **LibreOffice** (for PDF conversion):

```bash
brew install --cask libreoffice
```

- **poppler** (for PDF rasterization):

```bash
brew install poppler
```

After install, verify:
- `/Applications/LibreOffice.app/Contents/MacOS/soffice --version`
- `/opt/homebrew/bin/pdftoppm -v`

## Usage

```bash
# Convert a single file
python -m scorm_converter path/to/file.pptx

# Convert a single file, specify output dir
python -m scorm_converter path/to/file.docx --output ./my-output

# Recurse over a directory (mirrors folder structure under --output)
python -m scorm_converter path/to/course-folder/ --output ./output
```

Output packages are written to `./output/` by default (created if needed).
Lock files (`~$*.pptx`) are automatically skipped.

## Output location

```
output/
  Financial-Risk-Management.zip
  Activities.zip
  ...
```

## SCORM tracking behaviour

- **Completion rule:** `cmi.core.lesson_status = "completed"` is set once ALL
  slides have been visited (each slide is marked viewed when displayed).
- **Progress persistence:** The set of viewed slides is written to
  `cmi.suspend_data` so progress survives a session close and resume.
- **Progress UI:** A fixed bar at the top shows "Slide X / N" (current position)
  and "Viewed Y / N" (progress pill, turns green on completion).
- **Navigation:** Prev/Next buttons and Left/Right arrow keys.
- **Preloading:** Adjacent slides are preloaded in the background for snappy navigation.
- **Graceful degradation:** If no SCORM API is found (e.g., opening the HTML
  file directly or in a local dev server), slides still render and navigation
  still works — just no LMS data is reported.

## Testing locally (before LMS upload)

```bash
# Unzip the package and serve over HTTP
mkdir /tmp/test-scorm && unzip output/Financial-Risk-Management.zip -d /tmp/test-scorm
python3 -m http.server 8080 --directory /tmp/test-scorm
# Open http://localhost:8080/index.html in your browser
```

## LMS upload notes

- Upload the `.zip` file directly. The LMS will find `imsmanifest.xml` at the
  root and recognise it as a SCORM 1.2 package.
- The single SCO is configured with `adlcp:scormtype="sco"` and
  `href="index.html"`.
- No external network requests are made at runtime — all assets (JPEG images,
  `scorm_api.js`) are bundled inside the zip.
- No ES modules, no web workers — the viewer is a single classic `<script>` block
  that works even when the LMS content host serves files with incomplete MIME maps.
- Tested with LibreOffice 26.2.4.2 and poppler 26.06.0 on macOS (Apple Silicon).

## Project layout

```
scorm_converter/
  scorm_converter/
    __init__.py
    __main__.py       # python -m scorm_converter entry point
    cli.py            # argparse: file or directory, --output flag
    converter.py      # LibreOffice headless: source → PDF
    rasterizer.py     # pdftoppm: PDF → slide-001.jpg, slide-002.jpg, ...
    manifest.py       # build imsmanifest.xml
    packager.py       # orchestrate convert → rasterize → stage → zip
    templates/
      index.html      # image slide viewer + SCORM tracking (classic JS only)
      scorm_api.js    # SCORM 1.2 API discovery + wrapper
    schemas/          # SCORM 1.2 XSD schemas
    vendor/pdfjs/     # (legacy — not used in packages, kept on disk only)
  test_files/
  output/             # generated .zip packages
  README.md
```
