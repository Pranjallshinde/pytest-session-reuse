"""
conftest.py — Session-scoped Appium driver fixture for BrowserStack App Automate.

Key design decisions:
  - scope="session": ONE driver instance shared across ALL test methods in the run.
    The app is NOT reinstalled between tests (noReset=True).
  - Per-test status is reported manually via the BrowserStack executor so the
    session itself is never prematurely closed by the SDK between tests.
  - driver.quit() is called ONCE at the very end, which is when BrowserStack
    finalises the overall session.
  - Network profile changes remain valid throughout the session lifetime because
    the Appium session stays open until driver.quit().
"""

import json
import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options


def set_network_profile(driver, profile: str) -> None:
    """
    Change the BrowserStack network profile at any point during the session.

    Valid profiles (subset):
      '4g-lte-good', '4g-lte-lossy', '3g-umts-good', '3g-umts-lossy',
      '2g-gprs-good', 'no-network', 'edge-good', 'edge-lossy'

    Works throughout the session lifetime because the Appium session stays
    open until driver.quit() — no premature session closure between tests.

    """
    payload = json.dumps({
        "action": "update_network",
        "arguments": {"networkProfile": profile}
    })
    driver.execute_script(f"browserstack_executor: {payload}")


def mark_test_status(driver, status: str, reason: str = "") -> None:
    """
    Manually report per-test pass/fail to BrowserStack without closing the session.
    status: 'passed' or 'failed'
    """
    payload = json.dumps({
        "action": "setSessionStatus",
        "arguments": {"status": status, "reason": reason[:200]}
    })
    try:
        driver.execute_script(f"browserstack_executor: {payload}")
    except Exception:
        # Best-effort — never let status reporting crash the test
        pass


@pytest.fixture(scope="class")
def driver():
    """
    Class-scoped Appium driver fixture.

    - noReset=True  -> app is NOT reinstalled between test methods
    - driver.quit() -> called ONCE after all tests in the class finish
    """
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"

    # Prevent app reinstall between test methods
    options.no_reset = True

    # Allow invisible elements to be found (required for BrowserStack)
    options.set_capability("appium:allowInvisibleElements", True)

    import os
    bs_user = os.environ.get("BROWSERSTACK_USERNAME", "pranjalshinde_cZeuj6")
    bs_key  = os.environ.get("BROWSERSTACK_ACCESS_KEY", "zWqsnX9fetaDmPdGozNM")

    # BrowserStack-specific capabilities (device, project/build metadata)
    # These mirror browserstack.yml but must be set explicitly when using a
    # session-scoped fixture that the SDK plugin cannot intercept.
    # NOTE: "app" must be a top-level appium cap, NOT inside bstack:options.
    options.set_capability("bstack:options", {
        "userName": bs_user,
        "accessKey": bs_key,
        "deviceName": "Samsung Galaxy S23",
        "osVersion": "13.0",
        "projectName": "GS-Automation",
        "buildName": "Wikipedia-Session-Reuse",
        "networkLogs": True,
        "deviceLogs": True,
        "appiumLogs": True,
        "video": True,
    })
    # app must be set as a top-level capability
    options.set_capability("app", "bs://8f51b338b22320f9bd03095226efd3340c3050c0")

    driver_instance = webdriver.Remote(
        command_executor=f"https://{bs_user}:{bs_key}@hub.browserstack.com/wd/hub",
        options=options,
    )

    yield driver_instance

    # Called ONCE after all test methods finish.
    driver_instance.quit()
