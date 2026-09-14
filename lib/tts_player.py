"""Browser Web Speech TTS player with natural-voice preference."""

from __future__ import annotations

import html
import json

import streamlit.components.v1 as components

# Shared voice-selection logic for all TTS embeds.
_VOICE_JS = r"""
  function scoreVoice(v) {
    const name = (v.name || "").toLowerCase();
    const lang = (v.lang || "").toLowerCase();
    let score = 0;
    if (lang.startsWith("en")) score += 50;
    if (lang === "en-us" || lang === "en_us") score += 20;
    if (lang === "en-gb" || lang === "en_gb") score += 10;
    // Prefer neural / online / natural voices (Edge + Chrome)
    if (name.includes("neural")) score += 100;
    if (name.includes("natural")) score += 90;
    if (name.includes("online")) score += 80;
    if (name.includes("premium")) score += 70;
    if (name.includes("enhanced")) score += 60;
    if (name.includes("google")) score += 40;
    if (name.includes("microsoft")) score += 30;
    // Strong modern Microsoft voices
    ["aria", "jenny", "guy", "ryan", "sonia", "sara", "davis", "jane", "jason", "tony", "nancy"].forEach((n) => {
      if (name.includes(n)) score += 25;
    });
    // Avoid clearly robotic / compact voices
    if (name.includes("compact")) score -= 40;
    if (name.includes("eloquence")) score -= 20;
    if (v.localService === false) score += 35; // cloud/online voices often sound better
    return score;
  }

  function listVoices() {
    return window.speechSynthesis.getVoices().slice().sort((a, b) => scoreVoice(b) - scoreVoice(a));
  }

  function pickBestVoice(voices) {
    if (!voices.length) return null;
    const en = voices.filter((v) => (v.lang || "").toLowerCase().startsWith("en"));
    const pool = en.length ? en : voices;
    return pool.slice().sort((a, b) => scoreVoice(b) - scoreVoice(a))[0] || null;
  }

  function fillVoiceSelect(selectEl, preferredName) {
    const voices = listVoices();
    selectEl.innerHTML = "";
    if (!voices.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "Default system voice";
      selectEl.appendChild(opt);
      return null;
    }
    let selected = null;
    voices.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v.name;
      const tag = scoreVoice(v) >= 100 ? " ★" : (v.localService === false ? " (online)" : "");
      opt.textContent = v.name + " — " + v.lang + tag;
      selectEl.appendChild(opt);
    });
    if (preferredName && voices.some((v) => v.name === preferredName)) {
      selectEl.value = preferredName;
      selected = voices.find((v) => v.name === preferredName);
    } else {
      selected = pickBestVoice(voices);
      if (selected) selectEl.value = selected.name;
    }
    try { localStorage.setItem("su_mit_tts_voice", selectEl.value); } catch (e) {}
    return selected;
  }

  function resolveVoice(selectEl) {
    const voices = listVoices();
    const name = selectEl.value;
    return voices.find((v) => v.name === name) || pickBestVoice(voices);
  }
"""


def render_tts_player(text: str, *, height: int = 260) -> None:
    """Render a self-contained TTS control strip for the given article text."""
    if not text or not text.strip():
        components.html(
            """
            <div style="font-family: Georgia, 'Times New Roman', serif; color: #57534e; padding: 12px 4px;">
              No speakable text found for this item.
            </div>
            """,
            height=60,
        )
        return

    payload = json.dumps(text)
    components.html(
        f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  :root {{
    --ink: #1c1917;
    --muted: #57534e;
    --accent: #1a5f4a;
    --accent-soft: #d7ebe3;
    --border: #d6cbb8;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    color: var(--ink);
    background: transparent;
  }}
  .player {{
    background: linear-gradient(160deg, #f3eee4 0%, #e8dfd0 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 16px 12px;
  }}
  .row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }}
  button, select {{
    appearance: none;
    border: 1px solid var(--border);
    background: #fffdf8;
    color: var(--ink);
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 14px;
    cursor: pointer;
    max-width: 100%;
  }}
  #voice {{ min-width: 220px; max-width: 340px; }}
  button:hover {{ background: var(--accent-soft); border-color: var(--accent); }}
  button.primary {{
    background: var(--accent);
    color: #f7f3eb;
    border-color: var(--accent);
    font-weight: 600;
    min-width: 88px;
  }}
  button.primary:hover {{ filter: brightness(1.05); }}
  .status {{
    margin-top: 10px;
    font-size: 13px;
    color: var(--muted);
    line-height: 1.4;
  }}
  .tip {{
    margin-top: 6px;
    font-size: 12px;
    color: var(--muted);
  }}
  .progress {{
    margin-top: 8px;
    height: 4px;
    background: #ddd4c4;
    border-radius: 999px;
    overflow: hidden;
  }}
  .progress > span {{
    display: block;
    height: 100%;
    width: 0%;
    background: var(--accent);
    transition: width 0.2s ease;
  }}
  .label {{
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }}
</style>
</head>
<body>
  <div class="player">
    <div class="label">Listen</div>
    <div class="row">
      <button class="primary" id="playPause" type="button">Play</button>
      <button id="back" type="button" title="Rewind ~15s">−15s</button>
      <button id="forward" type="button" title="Jump forward ~15s">+15s</button>
      <button id="stop" type="button">Stop</button>
      <label for="voice" style="font-size:13px;color:var(--muted);">Voice</label>
      <select id="voice" aria-label="Voice"></select>
      <label for="rate" style="font-size:13px;color:var(--muted);">Speed</label>
      <select id="rate" aria-label="Playback speed">
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
    <div class="progress" aria-hidden="true"><span id="bar"></span></div>
    <div class="status" id="status">Ready</div>
    <div class="tip" id="tip">Tip: Microsoft Edge usually has the most natural “Neural” voices on Windows.</div>
  </div>
<script>
(function () {{
  const raw = {payload};
  if (!("speechSynthesis" in window)) {{
    document.getElementById("status").textContent =
      "Text-to-speech is not supported in this browser.";
    document.querySelectorAll("button, select").forEach((el) => (el.disabled = true));
    return;
  }}

  {_VOICE_JS}

  function splitSentences(text) {{
    const cleaned = text.replace(/\\s+/g, " ").trim();
    if (!cleaned) return [];
    const parts = cleaned.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [cleaned];
    return parts.map((s) => s.trim()).filter(Boolean);
  }}

  const sentences = splitSentences(raw);
  let index = 0;
  let rate = 1;
  let speaking = false;
  let paused = false;
  const SKIP = 3;
  let preferred = null;
  try {{ preferred = localStorage.getItem("su_mit_tts_voice"); }} catch (e) {{}}

  const playPauseBtn = document.getElementById("playPause");
  const statusEl = document.getElementById("status");
  const bar = document.getElementById("bar");
  const voiceSelect = document.getElementById("voice");
  const tip = document.getElementById("tip");

  function refreshVoices() {{
    fillVoiceSelect(voiceSelect, preferred || voiceSelect.value);
    preferred = voiceSelect.value;
    const best = resolveVoice(voiceSelect);
    if (best && /neural|natural|online/i.test(best.name)) {{
      tip.textContent = "Using a higher-quality voice: " + best.name;
    }} else {{
      tip.textContent = "Tip: Microsoft Edge usually has the most natural “Neural” voices on Windows.";
    }}
  }}

  function updateUI() {{
    const total = sentences.length || 1;
    const current = Math.min(index + 1, total);
    const pct = Math.round((index / total) * 100);
    bar.style.width = pct + "%";
    if (!sentences.length) {{
      statusEl.textContent = "Nothing to read.";
      playPauseBtn.textContent = "Play";
      return;
    }}
    const v = resolveVoice(voiceSelect);
    const vLabel = v ? v.name : "default";
    if (speaking && !paused) {{
      playPauseBtn.textContent = "Pause";
      statusEl.textContent = "Playing sentence " + current + " of " + total + " · " + rate + "× · " + vLabel;
    }} else if (paused) {{
      playPauseBtn.textContent = "Resume";
      statusEl.textContent = "Paused at sentence " + current + " of " + total;
    }} else {{
      playPauseBtn.textContent = "Play";
      statusEl.textContent =
        index >= sentences.length
          ? "Finished · " + total + " sentences"
          : "Ready · sentence " + current + " of " + total;
    }}
  }}

  function cancelSpeech() {{
    window.speechSynthesis.cancel();
  }}

  function speakFrom(start) {{
    cancelSpeech();
    index = Math.max(0, Math.min(start, sentences.length));
    speaking = false;
    paused = false;
    if (index >= sentences.length) {{
      updateUI();
      return;
    }}
    speaking = true;
    speakNext();
  }}

  function speakNext() {{
    if (index >= sentences.length) {{
      speaking = false;
      paused = false;
      updateUI();
      return;
    }}
    const u = new SpeechSynthesisUtterance(sentences[index]);
    u.rate = rate;
    u.pitch = 1;
    const voice = resolveVoice(voiceSelect);
    if (voice) u.voice = voice;
    u.onend = function () {{
      if (!speaking || paused) return;
      index += 1;
      updateUI();
      speakNext();
    }};
    u.onerror = function () {{
      speaking = false;
      paused = false;
      updateUI();
    }};
    window.speechSynthesis.speak(u);
    updateUI();
  }}

  playPauseBtn.addEventListener("click", function () {{
    if (!sentences.length) return;
    if (!speaking) {{
      speakFrom(index >= sentences.length ? 0 : index);
      return;
    }}
    if (paused) {{
      window.speechSynthesis.resume();
      paused = false;
      updateUI();
    }} else {{
      window.speechSynthesis.pause();
      paused = true;
      updateUI();
    }}
  }});

  document.getElementById("back").addEventListener("click", function () {{
    const wasPlaying = speaking && !paused;
    const next = Math.max(0, index - SKIP);
    if (wasPlaying || paused || speaking) {{
      speakFrom(next);
    }} else {{
      index = next;
      updateUI();
    }}
  }});

  document.getElementById("forward").addEventListener("click", function () {{
    const wasPlaying = speaking && !paused;
    const next = Math.min(sentences.length, index + SKIP);
    if (wasPlaying || paused || speaking) {{
      if (next >= sentences.length) {{
        cancelSpeech();
        speaking = false;
        paused = false;
        index = sentences.length;
        updateUI();
      }} else {{
        speakFrom(next);
      }}
    }} else {{
      index = next;
      updateUI();
    }}
  }});

  document.getElementById("stop").addEventListener("click", function () {{
    cancelSpeech();
    speaking = false;
    paused = false;
    index = 0;
    updateUI();
  }});

  document.getElementById("rate").addEventListener("change", function (e) {{
    rate = parseFloat(e.target.value) || 1;
    if (speaking && !paused) {{
      speakFrom(index);
    }} else {{
      updateUI();
    }}
  }});

  voiceSelect.addEventListener("change", function () {{
    preferred = voiceSelect.value;
    try {{ localStorage.setItem("su_mit_tts_voice", preferred); }} catch (e) {{}}
    tip.textContent = "Voice set to " + preferred;
    if (speaking && !paused) speakFrom(index);
    else updateUI();
  }});

  window.speechSynthesis.onvoiceschanged = refreshVoices;
  refreshVoices();
  // Some browsers populate voices asynchronously.
  setTimeout(refreshVoices, 250);
  setTimeout(refreshVoices, 1000);
  updateUI();
}})();
</script>
</body>
</html>
        """,
        height=height,
    )


def escape_for_display(text: str) -> str:
    return html.escape(text)
