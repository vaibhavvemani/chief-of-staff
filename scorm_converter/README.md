# BeyondRisX SCORM Converter

This is a small local web app that converts static `.docx` and `.pptx` files into SCORM 1.2 ZIP packages. It is designed for simple Word documents and PowerPoint decks with no animations or embedded video.

## What It Produces

Each input file becomes one ZIP package:

```text
output/
  my-course_scorm.zip
```

Inside the ZIP:

```text
imsmanifest.xml
index.html
scorm_api.js
assets/
```

The package launches `index.html`, initializes the LMS SCORM 1.2 API, tracks progress, and marks completion when the learner reaches the end.

## Supported Files

Supported now:

- `.docx`
- `.pptx`

Not supported yet:

- `.doc`
- `.ppt`

For legacy Office files, open them in Microsoft Office, Google Docs/Slides, or LibreOffice and save them as `.docx` or `.pptx` first.

## Setup

Use the bundled Python runtime if you are running this from Codex:

```bash
/Users/siddarthsrinivas/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scorm_converter/app.py
```

Or use your own Python 3 environment:

```bash
python3 scorm_converter/app.py
```

The app expects `python-docx` for Word conversion. It is already available in the bundled Codex runtime used during development. If your own Python does not have it:

```bash
python3 -m pip install python-docx
```

## How To Use

1. Start the app.
2. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
3. Select a folder containing `.docx` or `.pptx` files.
4. Click **Convert**.
5. Download each generated SCORM ZIP from the results list.

Generated packages are also written to:

```text
scorm_converter/output/
```

## Conversion Notes

For Word documents, the converter reads paragraphs, headings, tables, and embedded images.

For PowerPoint decks, the converter reads static slide text and embedded images from the `.pptx` file. It does not preserve precise PowerPoint positioning, speaker notes, transitions, animations, charts as editable objects, or video. Since your current decks do not use animations or video, this is a good first version.

## SCORM Behavior

The generated package uses SCORM 1.2 calls:

- `LMSInitialize`
- `LMSSetValue`
- `LMSCommit`
- `LMSFinish`

For slide decks, progress is updated as the learner moves through slides. The course is marked `completed` on the final slide.

For Word documents, the course is marked `completed` after load because there is no page boundary yet.

## Files

- `app.py` - local web server and upload/conversion endpoints
- `converter.py` - document parsing and SCORM package generation
- `static/index.html` - browser UI
- `output/` - generated SCORM ZIP files

## Future Improvements

- Add one combined SCORM package for an entire folder.
- Split long Word documents into pages and require reaching the final page before completion.
- Add LibreOffice support for `.doc`, `.ppt`, and higher-fidelity slide rendering.
- Add SCORM 2004 output mode.
