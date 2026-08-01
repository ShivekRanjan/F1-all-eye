"""Screenshot the running app for the README hero, via headless Chrome + CDP.

    python scripts/capture_shots.py                 # -> assets/shots/*.png
    python scripts/capture_shots.py --url http://localhost:5173

Then `scripts/make_demo_gif.py assets/shots` assembles them.

The point is that the hero stops being a manual chore. The previous one was four
screenshots taken by hand, which is why it sat three weeks stale showing a UI
that no longer existed — nobody re-does five screenshots to fix one panel. This
drives the real app against the real engine, so a regenerated hero is always the
app as it actually is.

Chrome is driven over the DevTools Protocol rather than through a screenshot
flag because two of the frames need *state*: the Ask view is only interesting
mid-conversation, and a conversation has to be typed. `--screenshot` cannot do
that; `Runtime.evaluate` can.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

from f1se.config import PROJECT_ROOT

OUT = PROJECT_ROOT / "assets" / "shots"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

# React controls the input, so assigning `.value` is invisible to it — the
# native setter plus a bubbling `input` event is what makes the component see a
# keystroke. Same reason a plain `.value =` silently does nothing in tests.
TYPE_AND_SEND = """
(async () => {
  const inp = document.querySelector('main input');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, %s);
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise(r => setTimeout(r, 120));
  document.querySelector('main button[type=submit]').click();
})()
"""

#: (filename, hash route, setup script or None, extra settle seconds)
SHOTS = [
    ("01-home.png", "#/home", None, 3),
    ("02-ask.png", "#/ask", "ASK", 2),
    ("03-strategy.png", "#/strategy", None, 12),
    ("04-racehub.png", "#/racehub", None, 12),
    ("05-standings.png", "#/standings", None, 6),
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    found = shutil.which("chrome") or shutil.which("google-chrome")
    if found:
        return found
    raise SystemExit("Chrome not found — pass --chrome /path/to/chrome")


class CDP:
    def __init__(self, ws):
        self.ws, self._id = ws, 0

    async def send(self, method: str, **params):
        self._id += 1
        await self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def js(self, expression: str, await_promise: bool = False):
        r = await self.send("Runtime.evaluate", expression=expression,
                            awaitPromise=await_promise, returnByValue=True)
        return r.get("result", {}).get("value")


async def wait_for(cdp: CDP, expression: str, timeout: float, what: str) -> bool:
    """Poll a page predicate. Returns False rather than raising — one view
    failing to settle should still leave the other four usable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if await cdp.js(expression):
                return True
        except RuntimeError:
            pass
        await asyncio.sleep(0.5)
    print(f"    !! timed out waiting for {what}")
    return False


async def run(base: str, out: Path, width: int, height: int, chrome: str) -> int:
    profile = tempfile.mkdtemp(prefix="f1se-shots-")
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--remote-debugging-port=9333", f"--user-data-dir={profile}",
         f"--window-size={width},{height}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(40):
            try:
                pages = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=2))
                ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        if not ws_url:
            raise SystemExit("headless Chrome never exposed a debugging target")

        out.mkdir(parents=True, exist_ok=True)
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
            cdp = CDP(ws)
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.send("Emulation.setDeviceMetricsOverride",
                           width=width, height=height, deviceScaleFactor=1, mobile=False)

            for name, route, setup, settle in SHOTS:
                print(f"  {name:18} {route}")
                await cdp.send("Page.navigate", url=f"{base}/{route}")
                await asyncio.sleep(1.5)
                # Hash-only changes are same-document, so nudge the router too.
                await cdp.js(f"window.location.hash = {json.dumps(route.lstrip('#'))}")
                await wait_for(cdp, "!!document.querySelector('main')", 20, "main")

                if setup == "ASK":
                    await cdp.js("sessionStorage.removeItem('f1se.ask.turns')")
                    await cdp.js("window.location.reload()")
                    await asyncio.sleep(2)
                    await wait_for(cdp, "!!document.querySelector('main input')", 20, "composer")
                    await cdp.js(TYPE_AND_SEND % json.dumps("fastest strategy for silverstone"),
                                 await_promise=True)
                    await wait_for(cdp, "document.querySelector('main').innerText.includes('British Grand Prix')",
                                   90, "the strategy answer")
                    await cdp.js(TYPE_AND_SEND % json.dumps("but the track temperature is 35 degrees"),
                                 await_promise=True)
                    await wait_for(cdp, "document.querySelector('main').innerText.includes('refinement')",
                                   90, "the refinement answer")

                await asyncio.sleep(settle)
                shot = await cdp.send("Page.captureScreenshot", format="png")
                (out / name).write_bytes(base64.b64decode(shot["data"]))
                print(f"    saved {(out / name).stat().st_size // 1024} KB")
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:5180", help="running frontend")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--chrome", default=None)
    args = ap.parse_args()
    print(f"capturing {args.url} at {args.width}x{args.height} -> {args.out}")
    return asyncio.run(run(args.url.rstrip("/"), args.out, args.width, args.height,
                           args.chrome or find_chrome()))


if __name__ == "__main__":
    sys.exit(main())
