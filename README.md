# SU MIT 26 — Class Library

Local Streamlit app for class **syllabus**, **readings**, **notes**, and **assignments**, organized by course.

## Setup

```powershell
.\su_mit_env\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run (laptop + phone on the same Wi‑Fi)

```powershell
streamlit run app.py
```

The app listens on **all interfaces** (`0.0.0.0:8501`) via [`.streamlit/config.toml`](.streamlit/config.toml).

- **Laptop:** [http://localhost:8501](http://localhost:8501)
- **Phone:** open `http://<your-laptop-ip>:8501` in the mobile browser

Find your laptop IP on Windows:

```powershell
ipconfig
```

Use the IPv4 address of the active Wi‑Fi adapter (for example `192.168.1.42`).

Allow Python/Streamlit through the Windows firewall if the phone cannot connect.

## Add content by course

Courses are registered for **26FQ**:

| Folder | Class |
|--------|--------|
| `content/TEED_5110/` | TEED 5110 · Sociopolitical Context Schools (Sec 01) |
| `content/TEED_5111/` | TEED 5111 · Justice Through The Arts (Sec 01) |
| `content/TEED_5112/` | TEED 5112 · Thriving Communities 1 (Sec 02) |
| `content/TEED_5113/` | TEED 5113 · Foundations Teach Cld Students (Sec 02) |
| `content/TEED_5114/` | TEED 5114 · Theory and Practice (Sec 01) |

Under each course:

| Path | Use |
|------|-----|
| `syllabus/` | Course syllabus |
| `readings/` | Articles and papers (`.md`, `.pdf`) |
| `notes/` | Your notes (`.md`, `.txt`) |
| `assignments/` | Prompts and handouts |

Use the top menu: **Class** → **Section** → class session → file.

## Project layout

```
app.py                 # Streamlit entry
lib/content.py         # Scan courses + load Markdown / files
lib/menubar.py         # Nested course navigation
content/<class>/...    # Your library files by class
.streamlit/config.toml # Theme + bind address
```
