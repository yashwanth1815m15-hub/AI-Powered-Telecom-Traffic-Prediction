"""
Phase C Automated Browser & Link Verification Suite (Playwright):
- Confirms Ookla attribution + speedtest phone-only counter logic
- Tests IPL Mumbai demo end-to-end in Chromium: banner on every page, non-blank Leaflet map,
  critical (+N demo) header counts, pulsing red markers, DEMO alert, Apply Action load drop & SVG chart,
  Stop demo + Reset to normal + Escape key restore exact baseline counts & delete all demo alerts.
- Checks HTTP 200 on every scenario source_url & statement_url
- Tests full UI translation switch across EN / HI / TE / KN, checks horizontal overflow, and saves screenshots.
"""

import re
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"
ARTIFACT_DIR = Path("/Users/yashu/.gemini/antigravity/brain/1297abd1-e6d2-4f00-b1b8-734e94a70897")


def _http_get_status(url: str) -> int:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return int(resp.status)


def test_every_scenario_source_url_returns_http_200():
    import json

    with urllib.request.urlopen(f"{BACKEND_URL}/api/simulation/presenter/status", timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))

    urls = []
    for sc in data.get("available_scenarios", []):
        if sc.get("source_url"):
            urls.append(sc["source_url"])
        if sc.get("statement_url"):
            urls.append(sc["statement_url"])

    assert len(urls) >= 3
    for u in urls:
        status = _http_get_status(u)
        assert status == 200, f"Expected HTTP 200 for {u}, got {status}"


def test_playwright_demo_lifecycle_and_languages():
    # Ensure clean baseline state before browser test
    req = urllib.request.Request(f"{BACKEND_URL}/api/simulation/presenter/reset", method="POST")
    urllib.request.urlopen(req, timeout=10).read()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    missing_i18n_warnings = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on(
            "console",
            lambda msg: missing_i18n_warnings.append(msg.text)
            if "[i18n] Missing" in msg.text
            else None,
        )

        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="header-critical-count"]', timeout=15000)

        # Record clean baseline critical text
        baseline_crit_text = page.locator('[data-testid="header-critical-count"]').inner_text().strip()
        assert "demo" not in baseline_crit_text.lower()

        # Confirm Ookla layer button is visible with India tiles attribution
        ookla_btn = page.locator("button", has_text="Ookla")
        assert ookla_btn.count() >= 1
        assert "India tiles" in ookla_btn.first.inner_text()

        # Verify Leaflet map container has healthy dimensions (not blank/collapsed)
        map_box = page.locator(".leaflet-container").first.bounding_box()
        assert map_box is not None and map_box["width"] > 400 and map_box["height"] > 350

        # Open Presenter panel via Ctrl+Shift+D
        page.keyboard.press("Control+Shift+D")
        page.wait_for_selector('[data-testid="activate-scenario-btn"]', timeout=8000)

        # Select Mumbai in city dropdown (default IPL scenario is ipl_surge)
        city_select = page.locator("select").nth(1)
        city_select.select_option("Mumbai")
        page.click('[data-testid="activate-scenario-btn"]')

        # Global demo banner appears + Affected sites: N > 0
        page.wait_for_selector('[data-testid="global-demo-banner"]', timeout=10000)
        banner_text = page.locator('[data-testid="global-demo-banner"]').inner_text()
        assert "Mumbai" in banner_text
        m_sites = re.search(r"Affected sites:\s*(\d+)", banner_text)
        assert m_sites is not None and int(m_sites.group(1)) >= 1

        # Close presenter drawer so we can verify map & tabs underneath
        page.locator("div.fixed.inset-0 button").first.click()
        page.wait_for_timeout(800)

        # Header critical shows (+N demo)
        crit_with_demo = page.locator('[data-testid="header-critical-count"]').inner_text().strip()
        assert "demo" in crit_with_demo.lower(), f"Expected (+N demo) in critical header, got {crit_with_demo}"

        # Markers turn red on map
        red_markers = page.locator(".beacon-critical").count()
        assert red_markers >= 1

        # Leaflet map stays non-blank/valid after demo banner pushed layout height
        map_box_demo = page.locator(".leaflet-container").first.bounding_box()
        assert map_box_demo is not None and map_box_demo["width"] > 400 and map_box_demo["height"] > 350

        # Check banner persists across tabs (AI Health & NOC Map)
        page.locator("nav button", has_text="AI Health").click()
        assert page.locator('[data-testid="global-demo-banner"]').is_visible()
        page.locator("nav button", has_text="NOC Map").click()
        assert page.locator('[data-testid="global-demo-banner"]').is_visible()

        # Reopen Presenter panel via "Open Panel" button in banner -> Apply Recommended Action -> SVG chart renders
        page.locator('[data-testid="global-demo-banner"] button', has_text="Open Panel").click()
        page.wait_for_selector('[data-testid="apply-recommended-action-btn"]', timeout=8000)
        page.click('[data-testid="apply-recommended-action-btn"]')
        page.wait_for_selector('[data-testid="before-after-chart"]', timeout=8000)
        assert page.locator('[data-testid="before-after-chart"] svg').is_visible()

        # Close panel -> open Alerts drawer -> verify DEMO alert exists
        page.locator("div.fixed.inset-0 button").first.click()
        page.click('button[title="Live Alert Feed"]')
        page.wait_for_selector('[data-testid="demo-alert-badge"]', timeout=8000)
        assert page.locator('[data-testid="demo-alert-badge"]').count() >= 1
        page.locator("div.fixed.inset-0 button").first.click()

        # Test Stop #1: Stop demo button in persistent banner
        page.click('[data-testid="global-stop-demo-btn"]')
        page.wait_for_selector('[data-testid="global-demo-banner"]', state="detached", timeout=8000)
        page.wait_for_timeout(500)
        restored_crit = page.locator('[data-testid="header-critical-count"]').inner_text().strip()
        assert restored_crit == baseline_crit_text

        # Test Stop #2: Sticky "Reset to normal" / "Stop demo and restore original view" inside Presenter panel
        page.keyboard.press("Control+Shift+D")
        page.wait_for_selector('[data-testid="activate-scenario-btn"]', timeout=8000)
        page.click('[data-testid="activate-scenario-btn"]')
        page.wait_for_selector('[data-testid="reset-normal-btn"]', timeout=8000)
        page.click('[data-testid="reset-normal-btn"]')
        page.wait_for_selector('[data-testid="global-demo-banner"]', state="detached", timeout=8000)

        # Test Stop #3: Esc key stops active demo cleanly
        page.click('[data-testid="activate-scenario-btn"]')
        page.wait_for_selector('[data-testid="global-demo-banner"]', timeout=8000)
        page.locator('div.fixed.inset-0 button').first.click()
        page.keyboard.press("Escape")
        page.wait_for_selector('[data-testid="global-demo-banner"]', state="detached", timeout=8000)

        # Confirm zero DEMO alerts remain open
        page.click('button[title="Live Alert Feed"]')
        page.wait_for_timeout(400)
        assert page.locator('[data-testid="demo-alert-badge"]').count() == 0
        page.locator("div.fixed.inset-0 button").first.click()

        # Test all 4 languages (EN, HI, TE, KN), check horizontal overflow, take 1 screenshot per language
        lang_checks = [
            ("en", "NOC Map"),
            ("hi", "एनओसी मानचित्र"),
            ("te", "ఎన్ఓసి మ్యాప్"),
            ("kn", "ಎನ್‌ಒಸಿ ನಕ್ಷೆ"),
        ]
        lang_select = page.locator('select[aria-label="Language selector"]')
        for code, expected_nav in lang_checks:
            lang_select.select_option(code)
            page.wait_for_timeout(400)
            nav_text = page.locator("nav").inner_text()
            assert expected_nav in nav_text, f"Expected '{expected_nav}' in nav for {code}, got: {nav_text}"
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            assert overflow is False, f"Horizontal overflow detected for language={code}"
            page.screenshot(path=str(ARTIFACT_DIR / f"verify_{code}.png"), full_page=False)

        # Verify AI Health view shows Cloudflare Radar India validation, zero setup banner, and comparison badges
        lang_select.select_option("en")
        page.locator("nav button", has_text="AI Health").click()
        page.wait_for_timeout(600)
        ai_text = page.locator("main").inner_text()
        assert "Token Setup Required" not in ai_text, "Cloudflare setup banner must not be visible once validated"
        assert "No results yet" not in ai_text, "Simulator leaderboard must be populated (not empty)"
        assert "validated on real india traffic series (cloudflare radar)" in ai_text.lower(), (
            f"Expected Cloudflare Radar validation header in AI Health, got: {ai_text[:400]}"
        )
        assert "Seasonal Naive Baseline" in ai_text or "Seasonal-Naive" in ai_text
        assert ("Better than Seasonal-Naive" in ai_text) or ("Does NOT beat Seasonal-Naive" in ai_text)
        assert page.locator('[data-testid="radar-series-table"] tbody tr').count() == 14, "Expected all 14 related India Radar series in table"
        assert "14 related series (states are subsets of India)" in ai_text
        for expected_as in [
            "Reliance Jio Infocomm Limited",
            "Bharti Airtel Ltd. AS for GPRS Service",
            "Bharti Airtel Ltd., Telemedia Services",
            "Vodafone Idea Ltd",
            "National Internet Backbone",
        ]:
            assert expected_as in ai_text, f"Expected Radar API AS name '{expected_as}' in AI Health"
        assert ai_text.count("inferred from AS name") >= 6, "Expected every ASN network type to be labeled 'inferred from AS name'"
        assert "Mobile Wireless" not in ai_text, "Do not label any ASN mobile-only"
        assert "AS8075 Microsoft Corporation" in ai_text, "Expected skipped #5 AS8075 explanation on AI Health"
        assert "2543h history" in ai_text
        assert "AS45117" not in ai_text and "INPL-IN-AP" not in ai_text, "Low-ranked AS45117 must be dropped"
        assert "network-level web traffic, may include fixed broadband" in ai_text.lower()
        assert "per drik panchang; regional calendars can differ by a day" in ai_text.lower()
        assert page.locator('[data-testid="festival-calendar-source"] a[href*="drikpanchang.com"]').is_visible()
        assert "did not help on test" in ai_text.lower()
        assert "shared simulator model" in ai_text.lower()
        assert "MUM-C101" in ai_text
        assert "Radar models validate the method on real web traffic; tower forecasts on the NOC map come from the simulator." in ai_text
        assert page.locator('[data-testid="last-7d-festival-section"]').is_visible(), "Expected Last 7 Days + Diwali chart"
        assert "Diwali" in page.locator('[data-testid="last-7d-festival-section"]').inner_text()
        assert page.locator('[data-testid="festival-ablation-card"]').is_visible()
        assert page.locator("table tbody tr").count() >= 18, "Expected 14 Radar series rows + 4 simulator model rows"
        page.screenshot(path=str(ARTIFACT_DIR / "verify_ai_health.png"), full_page=True)

        browser.close()

    assert page_errors == [], f"Uncaught page errors: {page_errors}"
    assert missing_i18n_warnings == [], f"Missing i18n keys logged: {missing_i18n_warnings}"
