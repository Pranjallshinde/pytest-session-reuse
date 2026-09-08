"""
test_wikipedia_session_reuse.py

Demonstrates session reuse across multiple test methods on BrowserStack App Automate:
  - Single Appium session shared across all test methods (noReset=True)
  - App is NOT reinstalled between tests
  - Network profile is changed mid-session without 422 errors
  - Per-test status reported via BrowserStack executor (mark_test_status)
  - BrowserStack session is only closed when driver.quit() is called (end of run)

Run with:
    browserstack-sdk pytest tests/test_wikipedia_session_reuse.py -v
"""

import sys
import os
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Ensure conftest helpers are importable from the tests/ subdirectory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import set_network_profile, mark_test_status


# ---------------------------------------------------------------------------
# Locators (Wikipedia Alpha — Android)
# ---------------------------------------------------------------------------
SEARCH_CONTAINER   = (AppiumBy.ID, "org.wikipedia.alpha:id/search_container")
SEARCH_FIELD       = (AppiumBy.ID, "org.wikipedia.alpha:id/search_src_text")
SEARCH_RESULTS     = (AppiumBy.ID, "org.wikipedia.alpha:id/search_results_list")
RESULT_TITLE       = (AppiumBy.ID, "org.wikipedia.alpha:id/page_list_item_title")
RESULT_DESCRIPTION = (AppiumBy.ID, "org.wikipedia.alpha:id/page_list_item_description")
SEARCH_CLOSE_BTN   = (AppiumBy.ID, "org.wikipedia.alpha:id/search_close_btn")
RECENT_PANEL       = (AppiumBy.ID, "org.wikipedia.alpha:id/search_panel_recent")
EMPTY_VIEW         = (AppiumBy.ID, "org.wikipedia.alpha:id/search_empty_view")
EMPTY_TEXT         = (AppiumBy.ID, "org.wikipedia.alpha:id/search_empty_text")
PAGE_TOOLBAR       = (AppiumBy.ID, "org.wikipedia.alpha:id/page_toolbar")
RESULT_CONTAINER   = (AppiumBy.ID, "org.wikipedia.alpha:id/page_list_item_container")
# Bottom nav tab — tapping this reliably returns to the Explore feed from any screen
EXPLORE_TAB        = (AppiumBy.ACCESSIBILITY_ID, "Explore")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def wait_for(driver, locator, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located(locator)
    )


def navigate_to_explore(driver):
    """Tap the Explore bottom-nav tab to reliably return to the Explore feed."""
    import time
    # Wait longer for Explore tab — app may be on splash/article screen
    wait_for(driver, EXPLORE_TAB, timeout=20).click()
    # Give the app a moment to transition before polling for search_container
    time.sleep(2)
    # Retry tap once if search_container not yet visible (handles slow transitions)
    try:
        wait_for(driver, SEARCH_CONTAINER, timeout=15)
    except Exception:
        wait_for(driver, EXPLORE_TAB, timeout=10).click()
        time.sleep(2)
        wait_for(driver, SEARCH_CONTAINER, timeout=20)


def open_search_and_type(driver, query: str):
    """Navigate to Explore, open search, and type a query."""
    navigate_to_explore(driver)
    wait_for(driver, SEARCH_CONTAINER).click()
    search_field = wait_for(driver, SEARCH_FIELD)
    search_field.send_keys(query)


# ---------------------------------------------------------------------------
# Tests — all share the single session-scoped driver fixture
# ---------------------------------------------------------------------------

class TestWikipediaSessionReuse:
    """
    All test methods share ONE BrowserStack session.
    The app is not reinstalled between methods (noReset=True).
    Network profile can be changed at any point — no 422 errors because
    the Appium session stays open until driver.quit() at the very end.
    """

    def test_01_search_valid_article(self, driver):
        """T003 — Search for Albert Einstein and verify results list."""
        try:
            open_search_and_type(driver, "Albert Einstein")

            wait_for(driver, SEARCH_RESULTS)

            titles = driver.find_elements(*RESULT_TITLE)
            assert len(titles) > 0, "No search result titles found"
            assert titles[0].text == "Albert Einstein", (
                f"Expected 'Albert Einstein', got '{titles[0].text}'"
            )

            descriptions = driver.find_elements(*RESULT_DESCRIPTION)
            assert len(descriptions) > 0, "No search result descriptions found"
            assert "German-born theoretical physicist" in descriptions[0].text, (
                f"Unexpected description: '{descriptions[0].text}'"
            )
            mark_test_status(driver, "passed", "Search results verified")
        except Exception as e:
            mark_test_status(driver, "failed", str(e))
            raise

    def test_02_open_article_page(self, driver):
        """T001 — Tap first result and verify article page opens."""
        try:
            # Results still visible from test_01 (session reuse, noReset=True)
            results = driver.find_elements(*RESULT_CONTAINER)
            assert len(results) > 0, "No search results visible — session state lost"
            results[0].click()

            toolbar = wait_for(driver, PAGE_TOOLBAR, timeout=20)
            assert toolbar.is_displayed(), "Article page toolbar not visible"
            mark_test_status(driver, "passed", "Article page opened")
        except Exception as e:
            mark_test_status(driver, "failed", str(e))
            raise

    def test_03_simulate_slow_network(self, driver):
        """
        Change network profile mid-session.
        This works because the Appium session stays open (noReset=True +
        session-scoped fixture). Without session reuse, BrowserStack would
        return 422 on this network API call after the first test completes.
        """
        try:
            # Tap Explore tab to return to feed from article page
            navigate_to_explore(driver)

            # Switch to slow network — session is still active
            set_network_profile(driver, "3g-umts-good")

            # Verify search still works on slow network
            open_search_and_type(driver, "Python")
            results_list = wait_for(driver, SEARCH_RESULTS, timeout=30)
            assert results_list.is_displayed(), "Search results not visible on slow network"
            mark_test_status(driver, "passed", "Network profile changed mid-session successfully")
        except Exception as e:
            mark_test_status(driver, "failed", str(e))
            raise

    def test_04_no_results_empty_state(self, driver):
        """T004 — Search gibberish and verify empty state."""
        try:
            # Return to Explore and open a fresh search
            open_search_and_type(driver, "xyzxyzxyzqqqqqq123")

            empty_view = wait_for(driver, EMPTY_VIEW)
            assert empty_view.is_displayed(), "Empty state view not shown for no-results query"

            empty_text = wait_for(driver, EMPTY_TEXT)
            assert empty_text.text == "No results found", (
                f"Expected 'No results found', got '{empty_text.text}'"
            )
            mark_test_status(driver, "passed", "Empty state verified")
        except Exception as e:
            mark_test_status(driver, "failed", str(e))
            raise

    def test_05_clear_search_restores_recent_panel(self, driver):
        """T005 — Clear search field and verify recent searches panel reappears."""
        try:
            # Still in search screen from test_04 — close button is visible
            close_btn = wait_for(driver, SEARCH_CLOSE_BTN)
            close_btn.click()

            search_field = wait_for(driver, SEARCH_FIELD)
            assert search_field.text in ("Search\u2026", ""), (
                f"Search field not cleared, contains: '{search_field.text}'"
            )

            recent_panel = wait_for(driver, RECENT_PANEL)
            assert recent_panel.is_displayed(), "Recent searches panel not visible after clearing"
            mark_test_status(driver, "passed", "Recent panel restored after clear")
        except Exception as e:
            mark_test_status(driver, "failed", str(e))
            raise

    def test_06_restore_network(self, driver):
        """Restore network to 4G — session still alive, no 422."""
        try:
            # Return to Explore screen via bottom nav tab
            navigate_to_explore(driver)

            # Restore network — session is still active
            set_network_profile(driver, "4g-lte-good")

            explore_search = wait_for(driver, SEARCH_CONTAINER, timeout=15)
            assert explore_search.is_displayed(), "Explore screen not visible after network restore"
            mark_test_status(driver, "passed", "Network restored to 4G, session still active")
        except Exception as e:
            mark_test_status(driver, "failed", str(e))
            raise
