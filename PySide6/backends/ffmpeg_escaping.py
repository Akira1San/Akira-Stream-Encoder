"""
Central escaping helpers for FFmpeg filter strings, concat demuxer files,
concat: protocol URLs, drawtext text, GStreamer parse_launch, and log formatting.

Why this module exists
----------------------
Subprocesses are launched with ``subprocess.Popen(cmd_list)`` (no shell), so
``-i`` / ``-o`` argv entries are safe with spaces and apostrophes. Breakage
happens where a path is *embedded as text* inside:

* ffmpeg ``-vf`` / ``-filter_complex`` strings
  (``subtitles='...'``, ``lut3d=file='...'``, ``drawtext=text='...'``)
* ffmpeg concat demuxer list files (``file '...'``)
* ffmpeg ``concat:`` protocol strings (``concat:a|b``)
* ``Gst.parse_launch("filesrc location=... ! ...")`` strings

The old code used the POSIX-shell idiom ``'\\''`` for filter strings, which is
only valid when a shell re-parses the string. Worse, empirical testing against
ffmpeg showed that *no* inline escaping passes a literal ``'`` through
ffmpeg's filter parser + ``subtitles`` filter: ``\\'`` inside ``'...'`` breaks
option parsing, ``'\\''`` gets mangled to nothing (file-not-found), and the
unquoted form re-exposes the Windows drive colon (misparsed as an option
separator). So files whose path contains ``'`` are *staged* to a safe-named
copy in the OS temp dir (:func:`prepare_filter_path`) and the safe copy is
burned instead. Concat demuxer files *do* use shell-like quoting, so ``'\\''``
(close-escape-reopen) is correct there and needs no staging.

All helpers are OS-agnostic (Windows + Linux): Windows paths are normalized to
forward slashes for ffmpeg, drive-letter colons are escaped, temp files use
``tempfile.gettempdir()`` (never hardcoded ``/tmp``), and files are written
UTF-8.
"""
import os
import re
import shlex
import subprocess


# ── FFmpeg filter paths (subtitles, LUT) ──────────────────────────────

def escape_filter_path(path: str) -> str:
    """Escape a file path for use inside ``'...'`` in an ffmpeg filter.

    Returns the path *including* the surrounding single quotes, ready to
    embed, e.g. ``f"subtitles={escape_filter_path(p)}"`` or
    ``f"lut3d=file={escape_filter_path(p)}"``.

    Rules (ffmpeg filter parser, same on Windows + Linux):
    * ``\\`` -> ``/`` (ffmpeg accepts forward slashes on Windows)
    * remaining ``\\`` -> ``\\\\``
    * ``:`` -> ``\\:``, ``,`` -> ``\\,``, ``;`` -> ``\\;``,
      ``[``/``]`` -> ``\\[``/``\\]``
    Drive-letter colons (``C:/``) are covered by the generic ``:`` escape,
    producing the widely used ``C\\:/...`` form.

    NOTE: a literal ``'`` cannot survive the filter parser in any inline form
    (verified empirically). Use :func:`prepare_filter_path` first to stage
    such files to a safe name, then escape the staged path here. As a safety
    net, a leftover ``'`` is still backslash-escaped (harmless when no real
    apostrophe round-trips, and correct for ``drawtext``-style consumers).
    """
    p = path.replace("\\", "/")
    p = p.replace("\\", "\\\\")
    p = p.replace("'", "\\'")
    p = p.replace(":", "\\:")
    p = p.replace(",", "\\,")
    p = p.replace(";", "\\;")
    p = p.replace("[", "\\[").replace("]", "\\]")
    return f"'{p}'"


# ── Filter-path staging (apostrophes) ───────────────────────────────

STAGE_DIR_NAME = "myencoder_filter_stage"


def needs_filter_staging(path: str) -> bool:
    """True when *path* cannot be embedded in a filter string as-is.

    Currently that is exactly the apostrophe case: no inline escaping passes
    a literal ``'`` through ffmpeg's filter parser + subtitles/LUT filters
    (verified with an ffmpeg repro matrix). All other metachars are handled
    by :func:`escape_filter_path`.
    """
    return "'" in path


def _stage_dir() -> str:
    import tempfile

    d = os.path.join(tempfile.gettempdir(), STAGE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _safe_stage_name(path: str) -> str:
    """Deterministic safe filename for *path* (reused across runs)."""
    import hashlib

    base = os.path.basename(path)
    stem, ext = os.path.splitext(base)
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", stem)[:60] or "file"
    digest = hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()[:12]
    # Keep subtitle/LUT extensions intact so filters sniff the format.
    return f"{safe_stem}_{digest}{ext}"


def _copy_to_stage(src: str, staged_name: str) -> str | None:
    """Copy *src* to the stage dir under *staged_name*; return staged path."""
    try:
        if not src or not os.path.isfile(src):
            return None
        dst = os.path.join(_stage_dir(), staged_name)
        if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
            import shutil

            shutil.copy2(src, dst)
        return dst
    except Exception:
        return None


def stage_file_for_filter(path: str) -> str | None:
    """Stage *path* to a filter-safe temp copy; return staged path or None.

    VobSub (``.sub``) is a pair: the sibling ``.idx`` is staged alongside
    under the same stem so the subtitles filter finds it.
    """
    staged_name = _safe_stage_name(path)
    staged = _copy_to_stage(path, staged_name)
    if staged is None:
        return None
    if path.lower().endswith(".sub"):
        idx_src = os.path.splitext(path)[0] + ".idx"
        if os.path.isfile(idx_src):
            idx_staged_name = os.path.splitext(staged_name)[0] + ".idx"
            _copy_to_stage(idx_src, idx_staged_name)
    return staged


def prepare_filter_path(path: str) -> tuple:
    """Return ``(usable_path, was_staged)`` for embedding in a filter.

    Paths without apostrophes are returned unchanged (escaping downstream
    handles them). Paths with apostrophes are copied to a safe-named temp
    file; callers should log the staging so the command log stays
    understandable. Never raises: on any failure the original path is
    returned unstaged.
    """
    try:
        if not needs_filter_staging(path):
            return path, False
        staged = stage_file_for_filter(path)
        if staged:
            return staged, True
    except Exception:
        pass
    return path, False


def stage_text_for_drawtext(text: str) -> str | None:
    """Stage overlay *text* to a temp file for ``drawtext=textfile=...``."""
    import hashlib

    try:
        name = f"drawtext_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}.txt"
        dst = os.path.join(_stage_dir(), name)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
        return dst
    except Exception:
        return None


def build_drawtext_text_arg(text: str) -> tuple:
    """Return ``(fragment, was_staged)`` for a drawtext text argument.

    Apostrophe-free text uses inline ``text='...'``; text containing ``'``
    is staged to a temp file referenced via ``textfile='...'`` since no
    inline escaping round-trips a literal quote.
    """
    try:
        if needs_filter_staging(text):
            staged = stage_text_for_drawtext(text)
            if staged:
                return f"textfile={escape_filter_path(staged)}", True
    except Exception:
        pass
    return f"text='{escape_drawtext_text(text)}'", False


# ── drawtext text ─────────────────────────────────────────────────────

def escape_drawtext_text(text: str) -> str:
    """Escape overlay text for ``drawtext=text='...'``.

    Text is not a path, so no slash/drive handling — only filter metachars.
    """
    t = text.replace("\\", "\\\\")
    t = t.replace("'", "\\'")
    t = t.replace(":", "\\:")
    t = t.replace(",", "\\,")
    t = t.replace(";", "\\;")
    t = t.replace("[", "\\[").replace("]", "\\]")
    t = t.replace("%", "\\%")
    return t


# ── Concat demuxer list files (``file '...'``) ────────────────────────

def escape_concat_path(path: str) -> str:
    """Escape a path for a ``file '...'`` line in a concat demuxer file.

    The concat demuxer uses shell-like single-quote grouping, so an embedded
    ``'`` is written as ``'\\''`` (close, escaped quote, reopen).
    """
    p = os.path.abspath(path)
    p = p.replace("\\", "/")
    p = p.replace("'", "'\\''")
    return p


def format_concat_line(path: str) -> str:
    """Return a complete ``file '...'`` line (with newline) for *path*."""
    return f"file '{escape_concat_path(path)}'\n"


def unescape_concat_path(escaped: str) -> str:
    """Reverse :func:`escape_concat_path` for paths read back from a list."""
    return escaped.replace("'\\''", "'")


def parse_concat_line(line: str):
    """Parse one ``file '...'`` line, returning the unescaped path or None."""
    m = re.match(r"file\s+'(.*)'\s*$", line.strip())
    if not m:
        return None
    return unescape_concat_path(m.group(1))


def write_concat_file(paths, suffix=".txt", prefix="ffmpeg_concat_") -> str:
    """Write *paths* to a UTF-8 concat list file; return its filename.

    Uses the platform temp dir (works on Windows + Linux) and UTF-8 so
    apostrophes / non-ASCII names survive.
    """
    import tempfile

    fd, concat_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(format_concat_line(p))
    return concat_path


# ── concat: protocol ──────────────────────────────────────────────────

def build_concat_protocol_input(paths) -> str | None:
    """Build a ``concat:a|b|c`` input, or None if unsafe.

    The ``concat:`` protocol splits on ``|`` with no escape mechanism, so any
    path containing ``|`` forces a fallback to the concat demuxer (caller
    should use :func:`write_concat_file` instead). Single quotes / spaces are
    passed through untouched — the whole string is one argv element, never
    re-parsed by a shell.
    """
    if not paths:
        return None
    for p in paths:
        if "|" in p:
            return None
    return "concat:" + "|".join(paths)


# ── GStreamer parse_launch ────────────────────────────────────────────

def quote_parse_launch_path(path: str) -> str:
    """Quote *path* for ``Gst.parse_launch("filesrc location=... ! ...")``.

    ``parse_launch`` re-parses the string shell-style, so bare
    ``location=/My Videos/Bob's/x.mp4`` splits/breaks. Double-quoting keeps
    spaces and single quotes literal on both OSes.
    """
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


# ── Log formatting (display only, never executed) ─────────────────────

def format_command_for_log(cmd) -> str:
    """Render an argv list for logs so copy-paste survives spaces/quotes.

    Uses ``subprocess.list2cmdline`` on Windows and ``shlex.join`` elsewhere.
    """
    try:
        if os.name == "nt" and hasattr(subprocess, "list2cmdline"):
            return subprocess.list2cmdline(cmd)
        if hasattr(shlex, "join"):
            return shlex.join(cmd)
        return " ".join(shlex.quote(c) for c in cmd)
    except Exception:
        return " ".join(str(c) for c in cmd)
