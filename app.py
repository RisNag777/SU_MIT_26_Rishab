"""SU MIT 26 — Class readings, notes, and assignments."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from lib.content import (
    ContentItem,
    course_label,
    course_subtitle,
    list_courses,
    load_markdown,
    load_text,
)
from lib.menubar import MENUBAR_CSS, render_menubar, resolve_item_from_params

st.set_page_config(
    page_title="SU MIT 26",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Source+Sans+3:wght@400;600&display=swap');

      html, body, [class*="css"] {
        font-family: "Source Sans 3", "Segoe UI", sans-serif;
      }
      .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 1100px;
      }
      section[data-testid="stSidebar"],
      button[data-testid="stSidebarCollapseButton"],
      [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
      }
      .item-meta {
        color: #78716c;
        font-size: 0.9rem;
        margin-bottom: 0.75rem;
      }
      .stApp {
        background:
          radial-gradient(1200px 500px at 10% -10%, #e4efe9 0%, transparent 55%),
          radial-gradient(900px 400px at 100% 0%, #f0e6d4 0%, transparent 50%),
          #f7f3eb;
      }
      .empty-hint {
        color: #57534e;
        margin-top: 1.5rem;
      }
    </style>
    """
    + MENUBAR_CSS,
    unsafe_allow_html=True,
)


def _pdf_iframe(path: Path) -> None:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    st.markdown(
        f"""
        <iframe
          title="PDF preview"
          src="data:application/pdf;base64,{b64}"
          width="100%"
          height="640"
          style="border:1px solid #d6cbb8;border-radius:12px;background:#fff;"
        ></iframe>
        """,
        unsafe_allow_html=True,
    )


def render_item(item: ContentItem) -> None:
    heading = item.title
    if item.session_label:
        st.caption(item.session_label)
    st.markdown(f"## {heading}")
    subtitle = course_subtitle(item.course)
    meta_bits = [course_label(item.course)]
    if subtitle:
        meta_bits.append(subtitle)
    meta_bits.extend([item.category, item.kind, f"`{item.relative}`"])
    st.markdown(
        f'<div class="item-meta">{" · ".join(meta_bits)}</div>',
        unsafe_allow_html=True,
    )

    if item.kind == "pdf":
        _pdf_iframe(item.path)
        st.download_button(
            "Download PDF",
            data=item.path.read_bytes(),
            file_name=item.path.name,
            mime="application/pdf",
        )
        return

    if item.kind == "document":
        st.info("Word `.doc` / `.docx` files can be downloaded below.")

    st.divider()

    if item.kind == "markdown":
        body = load_markdown(item.path)
        for url in _http_urls(body):
            st.link_button("Open link", url, type="primary")
        st.markdown(body)
    elif item.kind == "text":
        st.text(load_text(item.path))
    elif item.kind == "document":
        mime = (
            "application/msword"
            if item.path.suffix.lower() == ".doc"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        st.download_button(
            f"Download {item.path.suffix.upper()} file",
            data=item.path.read_bytes(),
            file_name=item.path.name,
            mime=mime,
        )


def _http_urls(text: str) -> list[str]:
    import re

    return list(dict.fromkeys(re.findall(r"https?://[^\s)\]]+", text)))


def _param(name: str) -> str | None:
    value = st.query_params.get(name)
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def main() -> None:
    courses = list_courses()
    course = _param("course")
    section = _param("section")
    session = _param("session")
    file_rel = _param("file")

    selected = resolve_item_from_params(course, section, session, file_rel)

    render_menubar(
        active_course=selected.course if selected else course,
        active_file=selected.relative if selected else file_rel,
    )

    if not courses:
        st.markdown(
            '<p class="empty-hint">Add a class folder under '
            "<code>content/</code>, then refresh.</p>",
            unsafe_allow_html=True,
        )
        return

    if selected is None:
        st.markdown(
            '<p class="empty-hint">Open a course (hover on desktop, tap on phone), then '
            "Syllabus / Readings / Notes / Assignments → class session → file.</p>",
            unsafe_allow_html=True,
        )
        return

    render_item(selected)


if __name__ == "__main__":
    main()
