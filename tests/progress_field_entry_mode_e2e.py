import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright

from tests.progress_fixed_workspace_production_e2e import BASE, PROJECT_ID, seed_progress, serve, stub


def main():
    seed_progress()
    server, thread = serve()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            stub(page)
            page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            expect(page.locator("#progressFieldEntryToggle")).to_be_visible(timeout=7000)

            for cycle in range(3):
                page.locator("#progressFieldEntryToggle").click()
                expect(page.locator("#progressFieldEntryOverlay")).to_be_visible(timeout=7000)
                expect(page.locator(".progress-field-entry-head")).to_have_count(0)

                frame = page.frame_locator("#progressFieldEntryFrame")
                expect(frame.locator("#progressEmbeddedBack")).to_be_visible(timeout=10000)
                expect(frame.locator("#progressEmbeddedBack")).to_have_count(1)
                expect(frame.locator(".controls")).to_be_visible()
                expect(frame.locator(".ui3-appbar")).not_to_be_visible()
                expect(frame.locator("#entrySmartFieldDraw")).to_be_visible(timeout=7000)
                expect(frame.locator("#entrySmartFieldDraw")).to_have_class("button active")

                metrics = frame.locator(".controls").evaluate("el=>({top:el.getBoundingClientRect().top,height:el.getBoundingClientRect().height})")
                assert abs(metrics["top"]) <= 1.5, (cycle, metrics)
                assert 46 <= metrics["height"] <= 50, (cycle, metrics)

                line = frame.locator("body").evaluate("""()=>{
                    const t=window.__weldSmartFieldDrawTest;
                    const pts=t.lineStrip({x:100,y:100},{x:1000,y:100});
                    return {pts, width:Math.hypot(pts[0].x-pts[3].x,pts[0].y-pts[3].y)};
                }""")
                assert len(line["pts"]) == 4, line
                assert line["width"] > 0, line

                placement = frame.locator("body").evaluate("""()=>{
                    const t=window.__weldSmartFieldDrawTest;
                    const host=window.__weldEntryAreaHost;
                    const p=t.markerCenter([{x:900,y:700},{x:1200,y:700},{x:1200,y:780},{x:900,y:780}]);
                    const hit=host.getCandidates().some(i=>p.x>=i.bbox.x&&p.x<=i.bbox.x+i.bbox.w&&p.y>=i.bbox.y&&p.y<=i.bbox.y+i.bbox.h);
                    return {p, hit};
                }""")
                assert placement["hit"] is False, (cycle, placement)

                frame.locator("#progressEmbeddedBack").click()
                expect(page.locator("#progressFieldEntryOverlay")).not_to_be_visible(timeout=7000)
                expect(page.locator("#progressFieldEntryToggle")).to_be_visible()

            expect(page.locator("#progressFieldEntryToggle")).to_have_count(1)
            expect(page.locator("#progressFieldEntryOverlay")).to_have_count(1)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("Progress field entry mode regression: PASS")


if __name__ == "__main__":
    main()
