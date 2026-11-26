# Lab manual

The generated deliverables are:

- `DevOps-and-Automation-Lab-Manual.pdf` - primary print/PDF deliverable with exact page numbers.
- `DevOps-and-Automation-Lab-Manual.docx` - editable Word version with the same layout.
- `DevOps-and-Automation-Lab-Manual.md` - plain-text source for review and diffing.
- `assets/university-logo.png` - the institutional emblem extracted from the supplied design.

The cover carries the exact requested details: Name `Arghyadipta Goswami`, Roll `2301010192`,
Section `C`, Year `2023-2027` and Subject `Dev Ops and Automation`. `tools/validate_repo.py`
re-checks those details in every generated format and rejects copied template text.

`tools/generate_lab_manual.py` and `tools/lab_manual_data.py` contain only original DevOps
capstone content. The supplied PDF was used solely to reproduce its visual design: centred cover,
blue title/rule, blue italic subtitle, student block, emblem placement, Table of Contents, small
italic running header, grey footer with page number, blue section headings, light-blue code
panels and bordered output tables. No IPCV experiment text, programs, outputs or figures were
copied.

Regenerate all three formats with:

```bash
make lab-manual
```
