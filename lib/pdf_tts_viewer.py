"""PDF viewers: clickable text PDFs (PDF.js) and scanned PDFs (page images)."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import streamlit.components.v1 as components

from lib.tts_player import _VOICE_JS  # noqa: PLC0414 — shared browser voice helpers

# Embedding very large PDFs in PDF.js often fails in Streamlit iframes.
_MAX_PDFJS_BYTES = 3_500_000
_MIN_TEXT_FOR_PDFJS = 800


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _pdf_page_image(path: Path, page_index: int, *, dpi: float = 110) -> bytes:
    """Render one PDF page to JPEG bytes (0-based page index)."""
    import fitz

    doc = fitz.open(path)
    try:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        return pix.tobytes("jpeg")
    finally:
        doc.close()


def _pdf_page_count(path: Path) -> int:
    import fitz

    doc = fitz.open(path)
    try:
        return doc.page_count
    finally:
        doc.close()


def _pdf_page_images(path: Path, *, dpi: float = 120, jpeg_quality: int = 60) -> list[str]:
    """Return base64 JPEG strings for each PDF page (legacy helper)."""
    import fitz

    doc = fitz.open(path)
    images: list[str] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_bytes = pix.tobytes("jpeg")
        images.append(base64.b64encode(img_bytes).decode("ascii"))
    doc.close()
    return images


def should_use_page_images(path: Path, text: str) -> bool:
    size = path.stat().st_size
    return size > _MAX_PDFJS_BYTES or len((text or "").strip()) < _MIN_TEXT_FOR_PDFJS


def render_pdf_tts_viewer(path: Path, text: str, *, height: int = 920) -> None:
    """Render a PDF for listening; uses page images for large/scanned files."""
    if should_use_page_images(path, text):
        render_scanned_pdf_viewer(path, text, height=height)
        return
    _render_pdfjs_viewer(path, text, height=height)


def render_scanned_pdf_viewer(path: Path, text: str, *, height: int = 920) -> None:
    """Show scanned/large PDFs as page images; OCR when needed for TTS."""
    import io

    import streamlit as st

    from lib.pdf_ocr import ensure_pdf_text, needs_ocr, ocr_cache_path, read_ocr_cache
    from lib.tts_player import render_tts_player

    try:
        total = _pdf_page_count(path)
    except Exception as exc:
        st.error(f"Could not open this PDF ({exc}). Use Download PDF below.")
        return

    display_text = text
    cache = read_ocr_cache(path)
    if cache:
        display_text = cache
        st.caption(f"Using OCR text (`{ocr_cache_path(path).name}`).")
    elif needs_ocr(path, text):
        st.info(
            "This PDF looks like a **scan**. Click **Convert pages to text (OCR)** "
            "once to extract readable/speakable text (saved next to the PDF)."
        )
        if st.button("Convert pages to text (OCR)", key=f"ocr-{abs(hash(path.as_posix()))}"):
            progress = st.progress(0.0, text="Starting OCR…")

            def _progress(page_i: int, page_total: int) -> None:
                progress.progress(
                    page_i / max(page_total, 1),
                    text=f"OCR page {page_i} of {page_total}…",
                )

            with st.spinner("Running OCR — first time can take a few minutes…"):
                display_text, source = ensure_pdf_text(
                    path, force_ocr=True, progress=_progress
                )
            progress.progress(1.0, text="OCR complete")
            if source == "ocr" and display_text:
                st.success(f"Extracted text saved to `{ocr_cache_path(path).name}`.")
                st.rerun()
            else:
                st.warning(
                    "OCR finished but found little text. Try Download PDF and a clearer scan."
                )

    if display_text.strip():
        render_tts_player(display_text)
        with st.expander("Extracted / OCR text", expanded=False):
            st.text(display_text)
    else:
        st.caption("No speakable text yet. Run OCR above if this is a scan.")

    key = f"pdf-page-{abs(hash(path.as_posix()))}"
    cols = st.columns([1, 1, 6])
    with cols[0]:
        if st.button("← Prev", key=f"{key}-prev", use_container_width=True):
            st.session_state[key] = max(1, int(st.session_state.get(key, 1)) - 1)
    with cols[1]:
        if st.button("Next →", key=f"{key}-next", use_container_width=True):
            st.session_state[key] = min(total, int(st.session_state.get(key, 1)) + 1)
    if key not in st.session_state:
        st.session_state[key] = 1
    st.session_state[key] = max(1, min(total, int(st.session_state[key])))
    page = int(st.session_state[key])

    st.caption(f"Page {page} of {total}")
    try:
        jpeg = _pdf_page_image(path, page - 1, dpi=130)
        st.image(io.BytesIO(jpeg), use_container_width=True)
    except Exception as exc:
        st.error(f"Could not render page {page} ({exc}).")
        try:
            import tempfile

            import fitz

            doc = fitz.open(path)
            pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            pix.save(tmp_path)
            doc.close()
            st.image(tmp_path, use_container_width=True)
        except Exception as exc2:
            st.error(f"Fallback render also failed ({exc2}).")


def _render_pdfjs_viewer(path: Path, text: str, *, height: int = 920) -> None:
    """PDF.js viewer with clickable text layer for text-based PDFs."""
    sentences = split_sentences(text)
    pdf_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    payload = json.dumps(
        {
            "sentences": sentences,
            "pdfBase64": pdf_b64,
            "embedPdf": True,
            "fileName": path.name,
        }
    )

    components.html(
        f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  :root {{
    --ink: #1c1917; --muted: #57534e; --accent: #1a5f4a;
    --accent-soft: #d7ebe3; --border: #d6cbb8;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: "Segoe UI", system-ui, sans-serif; color: var(--ink); background: transparent; }}
  .player {{
    background: linear-gradient(160deg, #f3eee4 0%, #e8dfd0 100%);
    border: 1px solid var(--border); border-radius: 14px; padding: 12px 14px;
    margin-bottom: 10px; position: sticky; top: 0; z-index: 5;
  }}
  .hint {{ font-size: 12px; color: var(--muted); margin: 0 0 8px 0; }}
  .row {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  button, select {{
    appearance: none; border: 1px solid var(--border); background: #fffdf8;
    color: var(--ink); border-radius: 10px; padding: 8px 12px; font-size: 14px; cursor: pointer;
  }}
  button:hover {{ background: var(--accent-soft); border-color: var(--accent); }}
  button.primary {{ background: var(--accent); color: #f7f3eb; border-color: var(--accent); font-weight: 600; min-width: 88px; }}
  .status {{ margin-top: 8px; font-size: 13px; color: var(--muted); }}
  .progress {{ margin-top: 8px; height: 4px; background: #ddd4c4; border-radius: 999px; overflow: hidden; }}
  .progress > span {{ display: block; height: 100%; width: 0%; background: var(--accent); }}
  #viewer {{
    border: 1px solid var(--border); border-radius: 12px; background: #ece7dc;
    max-height: 640px; overflow: auto; padding: 12px;
  }}
  .page {{ position: relative; margin: 0 auto 16px auto; box-shadow: 0 8px 24px rgba(28,25,23,0.12); background: #fff; width: fit-content; }}
  .page canvas {{ display: block; }}
  .textLayer {{ position: absolute; left: 0; top: 0; right: 0; bottom: 0; overflow: hidden; line-height: 1; }}
  .textLayer span {{ position: absolute; white-space: pre; transform-origin: 0% 0%; cursor: pointer; color: transparent; border-radius: 2px; }}
  .textLayer span:hover {{ background: rgba(26, 95, 74, 0.18); }}
  .textLayer span.active {{ background: rgba(253, 230, 138, 0.55); }}
  #fallback {{ display: none; border: 1px solid var(--border); border-radius: 12px; background: #fffdf8; max-height: 640px; overflow: auto; padding: 12px 14px; }}
  .sent {{ display: inline; cursor: pointer; border-radius: 4px; padding: 0 2px; line-height: 1.55; }}
  .sent:hover {{ background: rgba(26, 95, 74, 0.14); }}
  .sent.active {{ background: rgba(253, 230, 138, 0.7); }}
</style>
</head>
<body>
  <div class="player">
    <p class="hint">Click any text in the PDF to start listening from there.</p>
    <div class="row">
      <button class="primary" id="playPause" type="button">Play</button>
      <button id="back" type="button">−15s</button>
      <button id="forward" type="button">+15s</button>
      <button id="stop" type="button">Stop</button>
      <label for="voice" style="font-size:13px;color:var(--muted);">Voice</label>
      <select id="voice" style="max-width:280px;"></select>
      <label for="rate" style="font-size:13px;color:var(--muted);">Speed</label>
      <select id="rate">
        <option value="0.75">0.75×</option>
        <option value="0.9">0.9×</option>
        <option value="1" selected>1×</option>
        <option value="1.1">1.1×</option>
        <option value="1.25">1.25×</option>
        <option value="1.5">1.5×</option>
        <option value="1.75">1.75×</option>
        <option value="2">2×</option>
      </select>
    </div>
    <div class="progress"><span id="bar"></span></div>
    <div class="status" id="status">Ready</div>
  </div>
  <div id="viewer"></div>
  <div id="fallback"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script>
(function () {{
  const data = {payload};
  const sentences = data.sentences || [];
  let index = 0, rate = 1, speaking = false, paused = false;
  const SKIP = 3;
  let preferred = null;
  try {{ preferred = localStorage.getItem("su_mit_tts_voice"); }} catch (e) {{}}
  const playPauseBtn = document.getElementById("playPause");
  const statusEl = document.getElementById("status");
  const bar = document.getElementById("bar");
  const viewer = document.getElementById("viewer");
  const fallback = document.getElementById("fallback");
  const voiceSelect = document.getElementById("voice");

  {_VOICE_JS}

  function refreshVoices() {{
    fillVoiceSelect(voiceSelect, preferred || voiceSelect.value);
    preferred = voiceSelect.value;
  }}

  function normalize(s) {{ return (s || "").toLowerCase().replace(/\\s+/g, " ").trim(); }}
  function findSentenceIndex(clicked) {{
    const needle = normalize(clicked);
    if (!needle) return -1;
    let best = -1, bestScore = 0;
    for (let i = 0; i < sentences.length; i++) {{
      const hay = normalize(sentences[i]);
      if (!hay) continue;
      if (hay.includes(needle) || needle.includes(hay.slice(0, Math.min(40, hay.length)))) {{
        const score = Math.min(needle.length, hay.length);
        if (score > bestScore) {{ bestScore = score; best = i; }}
      }}
    }}
    return best;
  }}
  function updateUI() {{
    const total = sentences.length || 1;
    const current = Math.min(index + 1, total);
    bar.style.width = Math.round((index / total) * 100) + "%";
    document.querySelectorAll(".textLayer span.active, .sent.active").forEach((el) => el.classList.remove("active"));
    document.querySelectorAll('[data-si="' + index + '"]').forEach((el) => el.classList.add("active"));
    if (!sentences.length) {{ statusEl.textContent = "No speakable text found."; playPauseBtn.textContent = "Play"; return; }}
    if (speaking && !paused) {{ playPauseBtn.textContent = "Pause"; statusEl.textContent = "Playing sentence " + current + " of " + total + " · " + rate + "×"; }}
    else if (paused) {{ playPauseBtn.textContent = "Resume"; statusEl.textContent = "Paused at sentence " + current + " of " + total; }}
    else {{ playPauseBtn.textContent = "Play"; statusEl.textContent = index >= sentences.length ? "Finished · " + total + " sentences" : "Ready · sentence " + current + " of " + total + " · click PDF text to jump"; }}
  }}
  function cancelSpeech() {{ window.speechSynthesis.cancel(); }}
  function speakFrom(start) {{
    cancelSpeech(); index = Math.max(0, Math.min(start, sentences.length)); speaking = false; paused = false;
    if (index >= sentences.length) {{ updateUI(); return; }}
    speaking = true; speakNext();
  }}
  function speakNext() {{
    if (index >= sentences.length) {{ speaking = false; paused = false; updateUI(); return; }}
    const u = new SpeechSynthesisUtterance(sentences[index]);
    u.rate = rate;
    u.pitch = 1;
    const voice = resolveVoice(voiceSelect);
    if (voice) u.voice = voice;
    u.onend = function () {{ if (!speaking || paused) return; index += 1; updateUI(); speakNext(); }};
    u.onerror = function () {{ speaking = false; paused = false; updateUI(); }};
    window.speechSynthesis.speak(u); updateUI();
  }}
  playPauseBtn.addEventListener("click", function () {{
    if (!sentences.length) return;
    if (!speaking) {{ speakFrom(index >= sentences.length ? 0 : index); return; }}
    if (paused) {{ window.speechSynthesis.resume(); paused = false; updateUI(); }}
    else {{ window.speechSynthesis.pause(); paused = true; updateUI(); }}
  }});
  document.getElementById("back").addEventListener("click", function () {{
    const next = Math.max(0, index - SKIP);
    if (speaking || paused) speakFrom(next); else {{ index = next; updateUI(); }}
  }});
  document.getElementById("forward").addEventListener("click", function () {{
    const next = Math.min(sentences.length, index + SKIP);
    if (speaking || paused) {{
      if (next >= sentences.length) {{ cancelSpeech(); speaking = false; paused = false; index = sentences.length; updateUI(); }}
      else speakFrom(next);
    }} else {{ index = next; updateUI(); }}
  }});
  document.getElementById("stop").addEventListener("click", function () {{
    cancelSpeech(); speaking = false; paused = false; index = 0; updateUI();
  }});
  document.getElementById("rate").addEventListener("change", function (e) {{
    rate = parseFloat(e.target.value) || 1;
    if (speaking && !paused) speakFrom(index); else updateUI();
  }});
  voiceSelect.addEventListener("change", function () {{
    preferred = voiceSelect.value;
    try {{ localStorage.setItem("su_mit_tts_voice", preferred); }} catch (e) {{}}
    if (speaking && !paused) speakFrom(index); else updateUI();
  }});
  function onTextClick(rawText) {{
    const si = findSentenceIndex(rawText);
    if (si < 0) {{ statusEl.textContent = "Couldn't match that text — try a longer phrase."; return; }}
    speakFrom(si);
  }}
  function renderFallback() {{
    viewer.style.display = "none"; fallback.style.display = "block"; fallback.innerHTML = "";
    sentences.forEach((s, i) => {{
      const span = document.createElement("span"); span.className = "sent"; span.dataset.si = String(i);
      span.textContent = s + " "; span.addEventListener("click", () => speakFrom(i)); fallback.appendChild(span);
    }});
  }}
  async function renderPdf() {{
    if (!data.pdfBase64 || !window.pdfjsLib) {{ renderFallback(); return; }}
    pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    const raw = atob(data.pdfBase64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const pdf = await pdfjsLib.getDocument({{ data: bytes }}).promise;
    viewer.innerHTML = "";
    const scale = 1.15;
    for (let p = 1; p <= pdf.numPages; p++) {{
      const page = await pdf.getPage(p);
      const viewport = page.getViewport({{ scale }});
      const pageDiv = document.createElement("div");
      pageDiv.className = "page";
      pageDiv.style.width = viewport.width + "px";
      pageDiv.style.height = viewport.height + "px";
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width; canvas.height = viewport.height;
      pageDiv.appendChild(canvas);
      const textLayerDiv = document.createElement("div");
      textLayerDiv.className = "textLayer";
      pageDiv.appendChild(textLayerDiv);
      viewer.appendChild(pageDiv);
      await page.render({{ canvasContext: ctx, viewport }}).promise;
      const textContent = await page.getTextContent();
      textContent.items.forEach((item) => {{
        if (!item.str || !item.str.trim()) return;
        const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
        const span = document.createElement("span");
        span.textContent = item.str;
        span.title = "Click to listen from here";
        const fontHeight = Math.sqrt((tx[2] * tx[2]) + (tx[3] * tx[3]));
        span.style.left = tx[4] + "px";
        span.style.top = (tx[5] - fontHeight) + "px";
        span.style.fontSize = fontHeight + "px";
        span.style.fontFamily = "sans-serif";
        const si = findSentenceIndex(item.str);
        if (si >= 0) span.dataset.si = String(si);
        span.addEventListener("click", (ev) => {{ ev.preventDefault(); ev.stopPropagation(); onTextClick(item.str); }});
        textLayerDiv.appendChild(span);
      }});
    }}
  }}
  window.speechSynthesis.onvoiceschanged = refreshVoices;
  refreshVoices();
  setTimeout(refreshVoices, 250);
  setTimeout(refreshVoices, 1000);
  updateUI();
  renderPdf().catch((err) => {{ console.error(err); renderFallback(); }});
}})();
</script>
</body>
</html>
        """,
        height=height,
    )
