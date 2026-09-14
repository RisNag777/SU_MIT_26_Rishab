"""Nested menu bar: hover on desktop, tap on phone — Course → Section → Session → File."""

from __future__ import annotations

import html
from urllib.parse import urlencode

from lib.content import (
    CATEGORIES,
    ContentItem,
    course_label,
    list_courses,
    list_items,
    list_sessions,
    session_label,
)


def _file_href(course_id: str, section: str, session: str, item: ContentItem) -> str:
    params = {
        "course": course_id,
        "section": section,
        "file": item.relative,
    }
    if session:
        params["session"] = session
    return "?" + urlencode(params)


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def build_menubar_html(*, active_course: str | None = None, active_file: str | None = None) -> str:
    """Build nested menubar: hover on desktop, tap on touch devices."""
    courses = list_courses()
    course_tabs: list[str] = []

    for course_id in courses:
        short = course_label(course_id).split(" - ")[0]
        active_cls = " is-active" if course_id == active_course else ""
        open_attr = " open" if course_id == active_course else ""
        section_items: list[str] = []

        for section_name in CATEGORIES:
            sessions = list_sessions(course_id, section_name)
            has_sessions = any(sessions) or len(sessions) > 1

            if has_sessions:
                session_lis: list[str] = []
                for sess in sessions:
                    files = list_items(course_id, section_name, session=sess)
                    if not files:
                        session_lis.append(
                            f'<details class="menu-node">'
                            f"<summary>{_esc(session_label(sess))}</summary>"
                            f'<div class="panel-inner"><p class="empty">No files yet</p></div>'
                            f"</details>"
                        )
                        continue
                    file_lis = []
                    for item in files:
                        href = _file_href(course_id, section_name, sess, item)
                        file_active = " is-active" if item.relative == active_file else ""
                        file_lis.append(
                            f'<a class="file-link{file_active}" href="{_esc(href)}" target="_parent">'
                            f"{_esc(item.title)}</a>"
                        )
                    session_lis.append(
                        f'<details class="menu-node">'
                        f"<summary>{_esc(session_label(sess))}</summary>"
                        f'<div class="panel-inner">{"".join(file_lis)}</div>'
                        f"</details>"
                    )
                section_items.append(
                    f'<details class="menu-node">'
                    f"<summary>{_esc(section_name)}</summary>"
                    f'<div class="panel-inner">{"".join(session_lis)}</div>'
                    f"</details>"
                )
            else:
                files = list_items(course_id, section_name)
                if not files:
                    section_items.append(
                        f'<details class="menu-node">'
                        f"<summary>{_esc(section_name)}</summary>"
                        f'<div class="panel-inner"><p class="empty">No files yet</p></div>'
                        f"</details>"
                    )
                else:
                    file_lis = []
                    for item in files:
                        href = _file_href(course_id, section_name, "", item)
                        file_active = " is-active" if item.relative == active_file else ""
                        file_lis.append(
                            f'<a class="file-link{file_active}" href="{_esc(href)}" target="_parent">'
                            f"{_esc(item.title)}</a>"
                        )
                    section_items.append(
                        f'<details class="menu-node">'
                        f"<summary>{_esc(section_name)}</summary>"
                        f'<div class="panel-inner">{"".join(file_lis)}</div>'
                        f"</details>"
                    )

        course_tabs.append(
            f'<details class="course-tab{active_cls}"{open_attr}>'
            f'<summary class="course-btn">{_esc(short)}</summary>'
            f'<div class="panel-inner section-panel">{"".join(section_items)}</div>'
            f"</details>"
        )

    return f"""
<nav class="su-menubar" aria-label="Course library" data-mode="auto">
  <div class="su-brand">SU MIT 26</div>
  <div class="su-courses">
    {"".join(course_tabs)}
  </div>
</nav>
<script>
(function () {{
  const nav = document.querySelector(".su-menubar");
  if (!nav) return;

  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  let closeTimer = null;

  function isDesktopHover() {{
    return finePointer.matches;
  }}

  function closeAllCourses(except) {{
    nav.querySelectorAll(":scope > .su-courses > details.course-tab").forEach((el) => {{
      if (el !== except) el.open = false;
    }});
  }}

  function closeSiblingNodes(node) {{
    const parent = node.parentElement;
    if (!parent) return;
    parent.querySelectorAll(":scope > details.menu-node").forEach((sib) => {{
      if (sib !== node) sib.open = false;
    }});
  }}

  function clearCloseTimer() {{
    if (closeTimer) {{
      clearTimeout(closeTimer);
      closeTimer = null;
    }}
  }}

  function scheduleClose(course) {{
    clearCloseTimer();
    closeTimer = setTimeout(() => {{
      if (course && !course.matches(":hover")) course.open = false;
      nav.querySelectorAll("details.menu-node").forEach((n) => {{
        if (!n.matches(":hover")) n.open = false;
      }});
    }}, 180);
  }}

  // Accordion on tap (phone): one course open at a time.
  nav.querySelectorAll(":scope > .su-courses > details.course-tab").forEach((course) => {{
    course.addEventListener("toggle", () => {{
      if (!course.open) return;
      if (!isDesktopHover()) closeAllCourses(course);
    }});

    course.addEventListener("mouseenter", () => {{
      if (!isDesktopHover()) return;
      clearCloseTimer();
      closeAllCourses(course);
      course.open = true;
    }});
    course.addEventListener("mouseleave", () => {{
      if (!isDesktopHover()) return;
      scheduleClose(course);
    }});
  }});

  nav.querySelectorAll("details.menu-node").forEach((node) => {{
    node.addEventListener("toggle", () => {{
      if (!node.open) return;
      if (!isDesktopHover()) closeSiblingNodes(node);
    }});

    node.addEventListener("mouseenter", () => {{
      if (!isDesktopHover()) return;
      clearCloseTimer();
      closeSiblingNodes(node);
      node.open = true;
    }});
  }});

  // Keep panels open while moving into nested flyouts on desktop.
  nav.querySelectorAll(".section-panel, .menu-node > .panel-inner").forEach((panel) => {{
    panel.addEventListener("mouseenter", clearCloseTimer);
  }});

  finePointer.addEventListener("change", () => {{
    nav.dataset.mode = isDesktopHover() ? "hover" : "tap";
  }});
  nav.dataset.mode = isDesktopHover() ? "hover" : "tap";
}})();
</script>
"""


MENUBAR_CSS = """
<style>
  .block-container,
  .stMainBlockContainer,
  div[data-testid="stVerticalBlock"],
  div[data-testid="element-container"],
  .stMarkdown,
  .stMarkdown > div {
    overflow: visible !important;
  }

  .su-menubar {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 0.35rem 0.5rem;
    background: linear-gradient(160deg, #efe8dc 0%, #e7dece 100%);
    border: 1px solid #d6cbb8;
    border-radius: 14px;
    padding: 0.45rem 0.65rem;
    margin-bottom: 1rem;
    position: relative;
    z-index: 1000;
    font-family: "Source Sans 3", "Segoe UI", sans-serif;
  }
  .su-brand {
    font-family: Fraunces, Georgia, serif;
    font-weight: 700;
    font-size: 1.25rem;
    letter-spacing: -0.02em;
    color: #1c1917;
    padding: 0.45rem 0.7rem 0.45rem 0.35rem;
    display: flex;
    align-items: center;
    margin-right: 0.25rem;
    border-right: 1px solid #d6cbb8;
    min-height: 2.4rem;
  }
  .su-courses {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
    align-items: flex-start;
    flex: 1;
    min-width: 0;
  }
  .course-tab {
    position: relative;
  }
  .course-tab > summary.course-btn,
  .menu-node > summary {
    list-style: none;
    cursor: pointer;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  .course-tab > summary.course-btn::-webkit-details-marker,
  .menu-node > summary::-webkit-details-marker {
    display: none;
  }
  .course-tab > summary.course-btn {
    border: 1px solid transparent;
    background: transparent;
    color: #1c1917;
    font: inherit;
    font-size: 0.92rem;
    font-weight: 600;
    padding: 0.5rem 0.75rem;
    border-radius: 9px;
    white-space: nowrap;
    display: inline-block;
  }
  .course-tab[open] > summary.course-btn,
  .course-tab.is-active > summary.course-btn {
    background: #fffdf8;
    border-color: #d6cbb8;
  }
  .course-tab > .panel-inner.section-panel {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 220px;
    max-width: min(92vw, 320px);
    background: #fffdf8;
    border: 1px solid #d6cbb8;
    border-radius: 10px;
    box-shadow: 0 12px 28px rgba(28, 25, 23, 0.14);
    padding: 0.35rem;
    z-index: 1100;
  }

  /* Desktop: nested panels fly out to the right */
  @media (hover: hover) and (pointer: fine) {
    .menu-node {
      position: relative;
      margin: 0.1rem 0;
    }
    .menu-node > .panel-inner {
      display: none;
      position: absolute;
      top: 0;
      left: calc(100% - 2px);
      min-width: 200px;
      max-width: 280px;
      background: #fffdf8;
      border: 1px solid #d6cbb8;
      border-radius: 10px;
      box-shadow: 0 12px 28px rgba(28, 25, 23, 0.14);
      padding: 0.35rem;
      z-index: 1200;
      margin: 0;
      border-left: 1px solid #d6cbb8;
    }
    .menu-node[open] > .panel-inner {
      display: block;
    }
    .menu-node > summary::after {
      content: "›";
      color: #1a5f4a;
      font-size: 1.05rem;
    }
    .menu-node[open] > summary::after {
      transform: none;
    }
  }

  /* Phone / touch: stacked accordion */
  @media (hover: none), (pointer: coarse) {
    .menu-node {
      margin: 0.1rem 0;
    }
    .menu-node > .panel-inner {
      padding: 0.15rem 0.15rem 0.15rem 0.55rem;
      border-left: 2px solid #d7ebe3;
      margin: 0.15rem 0 0.25rem 0.45rem;
    }
    .menu-node > summary::after {
      content: "›";
      color: #1a5f4a;
      font-size: 1.05rem;
      transition: transform 0.15s ease;
    }
    .menu-node[open] > summary::after {
      transform: rotate(90deg);
    }
  }

  .menu-node > summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.55rem 0.65rem;
    border-radius: 8px;
    color: #1c1917;
    font-size: 0.9rem;
  }
  .menu-node[open] > summary {
    background: #d7ebe3;
  }
  .file-link {
    display: block;
    padding: 0.55rem 0.65rem;
    border-radius: 8px;
    color: #1c1917;
    text-decoration: none;
    font-size: 0.88rem;
    line-height: 1.35;
  }
  .file-link:hover,
  .file-link:active,
  .file-link.is-active {
    background: #d7ebe3;
    color: #134736;
  }
  .panel-inner .empty {
    color: #78716c;
    font-style: italic;
    font-size: 0.88rem;
    margin: 0.35rem 0.5rem;
  }

  @media (max-width: 720px) {
    .su-menubar {
      flex-direction: column;
      align-items: stretch;
    }
    .su-brand {
      border-right: none;
      border-bottom: 1px solid #d6cbb8;
      margin-right: 0;
      padding-bottom: 0.55rem;
    }
    .su-courses {
      flex-direction: column;
      width: 100%;
    }
    .course-tab > summary.course-btn {
      display: block;
      width: 100%;
    }
    .course-tab > .panel-inner.section-panel {
      position: static;
      max-width: none;
      width: 100%;
      box-shadow: none;
      margin-top: 0.25rem;
    }
  }
</style>
"""


def render_menubar(*, active_course: str | None = None, active_file: str | None = None) -> None:
    """Render the menubar in a component iframe so hover/tap JS can run."""
    import streamlit.components.v1 as components

    body = build_menubar_html(active_course=active_course, active_file=active_file)
    # Tall enough for desktop flyouts; phone accordion grows inside the frame.
    components.html(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
{MENUBAR_CSS}
<style>
  html, body {{ margin: 0; background: transparent; }}
  .su-menubar {{ margin-bottom: 0; }}
</style>
</head><body>
{body}
</body></html>""",
        height=320,
        scrolling=True,
    )


def resolve_item_from_params(
    course: str | None,
    section: str | None,
    session: str | None,
    file_rel: str | None,
) -> ContentItem | None:
    """Resolve a ContentItem from query-parameter navigation."""
    if not course or course not in list_courses():
        return None
    if section not in CATEGORIES:
        section = "Readings"
    if file_rel:
        for item in list_items(course, section):
            if item.relative == file_rel:
                return item
        for item in list_items(course, section):
            if item.path.name == file_rel or item.title == file_rel:
                return item
    if session is not None and session != "":
        items = list_items(course, section, session=session)
        return items[0] if items else None
    items = list_items(course, section)
    return items[0] if items else None
