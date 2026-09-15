"""Scan and load class library content (Markdown + PDF)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONTENT_ROOT = Path(__file__).resolve().parent.parent / "content"

CATEGORIES = {
    "Syllabus": "syllabus",
    "Readings": "readings",
    "Notes": "notes",
    "Assignments": "assignments",
}

SUPPORTED_SUFFIXES = {".md", ".markdown", ".pdf", ".txt", ".doc", ".docx"}

# Folder id -> catalog metadata (26FQ MIT cohort)
COURSES: dict[str, dict[str, str | int]] = {
    "TEED_5110": {
        "sl_no": 1,
        "code": "TEED 5110",
        "section": "01",
        "term": "26FQ",
        "name": "Sociopolitical Context Schools",
    },
    "TEED_5111": {
        "sl_no": 2,
        "code": "TEED 5111",
        "section": "01",
        "term": "26FQ",
        "name": "Justice Through The Arts",
    },
    "TEED_5112": {
        "sl_no": 3,
        "code": "TEED 5112",
        "section": "02",
        "term": "26FQ",
        "name": "Thriving Communities 1",
    },
    "TEED_5113": {
        "sl_no": 4,
        "code": "TEED 5113",
        "section": "02",
        "term": "26FQ",
        "name": "Foundations Teach Cld Students",
    },
    "TEED_5114": {
        "sl_no": 5,
        "code": "TEED 5114",
        "section": "01",
        "term": "26FQ",
        "name": "Theory and Practice",
    },
}


def _session_display_label(session: str) -> str:
    """Human-readable session folder (e.g. Class 1 - 9/3/26)."""
    if not session:
        return "General"
    label = session
    if " - " in label:
        prefix, rest = label.rsplit(" - ", 1)
        parts = rest.split("-")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            label = f"{prefix} - {parts[0]}/{parts[1]}/{parts[2]}"
    return label


def _session_sort_key(session: str) -> tuple:
    import re

    match = re.search(r"Class\s+(\d+)", session, re.IGNORECASE)
    num = int(match.group(1)) if match else 999
    return (0 if session else 1, num, session.lower())


@dataclass(frozen=True)
class ContentItem:
    course: str
    category: str
    path: Path
    title: str
    kind: str  # "markdown" | "pdf" | "text" | "document" | "link"
    session: str = ""  # optional subfolder under the category (e.g. Class 1)

    @property
    def relative(self) -> str:
        return str(self.path.relative_to(CONTENT_ROOT)).replace("\\", "/")

    @property
    def session_label(self) -> str:
        return _session_display_label(self.session)

    @property
    def picker_label(self) -> str:
        return self.title


def _title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def _display_name(folder_name: str) -> str:
    return folder_name.replace("_", " ").replace("-", " ").strip() or folder_name


def _kind_for(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".txt":
        return "text"
    if suffix in {".doc", ".docx"}:
        return "document"
    return None


def _session_for(path: Path, category_folder: Path) -> str:
    try:
        rel = path.parent.relative_to(category_folder)
    except ValueError:
        return ""
    if str(rel) in {".", ""}:
        return ""
    # Only use the top-level session folder (Class 1 - 9-3-26), not deeper nesting.
    return rel.parts[0]


def ensure_registered_courses() -> None:
    """Create syllabus/readings/notes/assignments folders for every registered course."""
    for course_id in COURSES:
        ensure_course_folders(course_id)


def list_courses() -> list[str]:
    """Return registered course folder ids in catalog order (creates folders if needed)."""
    ensure_registered_courses()
    return sorted(
        COURSES.keys(),
        key=lambda cid: int(COURSES[cid]["sl_no"]),
    )


def course_label(course_id: str) -> str:
    meta = COURSES.get(course_id)
    if not meta:
        return _display_name(course_id)
    return f"{meta['code']} - {meta['name']}"


def course_subtitle(course_id: str) -> str | None:
    meta = COURSES.get(course_id)
    if not meta:
        return None
    return f"Section {meta['section']} · {meta['term']}"


def list_items(
    course_id: str,
    category_label: str,
    *,
    session: str | None = None,
) -> list[ContentItem]:
    folder_name = CATEGORIES[category_label]
    folder = CONTENT_ROOT / course_id / folder_name
    if not folder.is_dir():
        return []

    items: list[ContentItem] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(".ocr.txt"):
            continue
        kind = _kind_for(path)
        if kind is None:
            continue
        item_session = _session_for(path, folder)
        if session is not None and item_session != session:
            continue
        items.append(
            ContentItem(
                course=course_id,
                category=category_label,
                path=path,
                title=_title_from_path(path),
                kind=kind,
                session=item_session,
            )
        )
    return items


def list_sessions(course_id: str, category_label: str) -> list[str]:
    """Return session subfolder names under a category (empty string = files at root)."""
    items = list_items(course_id, category_label)
    sessions = {item.session for item in items}
    return sorted(sessions, key=_session_sort_key)


def session_label(session: str) -> str:
    return _session_display_label(session)


def ensure_course_folders(course_id: str) -> Path:
    """Create syllabus/readings/notes/assignments under a course folder; return course path."""
    course_path = CONTENT_ROOT / course_id
    for folder_name in CATEGORIES.values():
        (course_path / folder_name).mkdir(parents=True, exist_ok=True)
    return course_path


def load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
