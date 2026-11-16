"""Patches app/src/Live.tsx and app/src/e2e.test.tsx in place (BUG-001 + Node 24 FormData fix).
Run from the repo root:  python apply_bug001_fix.py   (safe to re-run)"""
import pathlib, re, sys

root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
live = root / "app" / "src" / "Live.tsx"
e2e = root / "app" / "src" / "e2e.test.tsx"

s = live.read_text(encoding="utf-8")
s = re.sub(r"const STATE_TONE.*?\n\};\n\n", "", s, count=1, flags=re.S)
s = re.sub(r"[ \t]*const tone = snap \?[^\n]*\n", "", s, count=1)
s = re.sub(r"[ \t]*\{phase === \"running\" && snap && \(\n\s*<p className=\"tracking-label\">.*?</p>\n\s*\)\}\n", "", s, count=1, flags=re.S)
live.write_text(s, encoding="utf-8")

t = e2e.read_text(encoding="utf-8")
if "fixBody" not in t:
    old_fetch = '''    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      real(typeof input === "string" && input.startsWith("/api") ? `${URL_}${input}` : input, init)) as typeof fetch;'''
    new_fetch = '''    // Node >= 24 cannot serialise jsdom's FormData (the server then sees no fields: "no PGN provided").
    // The app only sends text fields in this test, so send them urlencoded; FastAPI Form() accepts both.
    const fixBody = (init?: RequestInit): RequestInit | undefined => {
      if (!init || typeof FormData === "undefined" || !(init.body instanceof FormData)) return init;
      const params = new URLSearchParams();
      init.body.forEach((v, k) => params.append(k, String(v)));
      return { ...init, body: params.toString(), headers: { "Content-Type": "application/x-www-form-urlencoded" } };
    };
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      real(typeof input === "string" && input.startsWith("/api") ? `${URL_}${input}` : input, fixBody(init))) as typeof fetch;'''
    old_assert = "    expect(screen.getByText(/Board locked|Move detected/)).toBeTruthy();\n  }, 60000);"
    new_assert = '''    // BUG-001: exactly one status display (the overlay badge); the legacy tracking label is gone
    expect(screen.getAllByTestId("overlay-status")).toHaveLength(1);
    expect(document.querySelector(".tracking-label")).toBeNull();
    expect(screen.getByText(/Board locked|Move detected/)).toBeTruthy();
  }, 60000);'''
    assert old_fetch in t and old_assert in t, "e2e.test.tsx is not the expected original; patch by hand"
    t = t.replace(old_fetch, new_fetch).replace(old_assert, new_assert)
    e2e.write_text(t, encoding="utf-8")

l = live.read_text(encoding="utf-8")
assert "tracking-label" not in l and "STATE_TONE" not in l and "const tone" not in l, "Live.tsx patch failed"
print("OK: Live.tsx and e2e.test.tsx patched")
