"""Local-only interaction check for the four-screen UI mock."""

from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parent


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        print(f"Chromium {browser.version}")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto((ROOT / "index.html").resolve().as_uri())
        assert page.locator("#intake.active").count() == 1
        assert page.locator("#start-processing").is_disabled()

        page.locator("#load-demo").click()
        assert page.locator(".case-row").count() == 4
        page.locator(".case-row").nth(3).click()
        page.locator("#cancel-case").click()
        assert "取消" in page.locator(".case-row").nth(3).inner_text()
        page.locator("#edit-case").click()
        page.locator("#log-file").set_input_files(
            ROOT.parent.parent / "samples" / "t006" / "normal-b.txt"
        )
        assert page.locator(".case-row").count() == 4
        assert "normal-b.txt" in page.locator(".case-row").nth(3).inner_text()
        page.locator("#load-demo").click()
        page.screenshot(path=str(ROOT / "review-01-intake.png"), full_page=True)
        page.locator("#start-processing").click()
        assert page.locator("#progress.active").count() == 1
        assert page.locator("#progress-cards .card").count() == 4
        assert page.locator("#progress-cards .card").first.locator(".status").count() == 6
        assert "未確認" in page.locator("#progress-cards .card").first.inner_text()
        page.screenshot(path=str(ROOT / "review-02-progress.png"), full_page=True)

        page.locator("#confirm-excel").click()
        page.locator("#progress-cards .card").first.locator("[data-open-case]").click()
        assert page.locator("#case-detail.active").count() == 1
        page.locator('input[name="compare"][value="一致"]').check()
        page.locator('input[name="judgment"][value="正常"]').check()
        page.locator("#record-check").click()
        assert page.locator("#request-review").is_enabled()
        page.screenshot(path=str(ROOT / "review-03-case.png"), full_page=True)
        page.locator("#request-review").click()

        page.locator("#progress-cards .card").first.locator("[data-open-review]").click()
        assert page.locator("#review.active").count() == 1
        page.locator("#switch-role").click()
        page.locator('input[name="review-result"][value="差し戻し"]').check()
        page.locator("#return-reason").fill("架空の照合理由を追記してください")
        page.screenshot(path=str(ROOT / "review-04-review.png"), full_page=True)
        page.locator("#save-review").click()
        assert "差し戻し" in page.locator("#progress-cards .card").first.inner_text()

        page.locator("#progress-cards .card").first.locator("[data-open-case]").click()
        page.locator("#comment").fill("架空の補足を追記")
        page.locator("#record-check").click()
        assert page.locator("#request-review").inner_text() == "再依頼"
        page.locator("#request-review").click()
        page.locator("#progress-cards .card").first.locator("[data-open-review]").click()
        page.locator("#switch-role").click()
        page.locator('input[name="review-result"][value="確認済み"]').check()
        page.locator("#save-review").click()
        assert "確認済み" in page.locator("#progress-cards .card").first.inner_text()

        failed = page.locator("#progress-cards .card").nth(3)
        assert "停止" in failed.inner_text()
        failed.locator("[data-open-case]").click()
        assert page.locator("#retry-case").is_enabled()
        page.locator("#retry-case").click()
        assert "処理完了" in page.locator("#progress-cards .card").nth(3).inner_text()
        assert "未確認" in page.locator("#progress-cards .card").nth(3).inner_text()

        page.locator("#unknown-result").click()
        assert "結果未確認" in page.locator("#progress-cards .card").nth(1).inner_text()
        page.locator("#progress-cards .card").nth(1).locator("[data-open-case]").click()
        assert page.locator("#retry-case").is_disabled()
        page.locator("#case-back").click()

        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#back-intake").click()
        assert page.locator("#environment").input_value() == "架空環境C"
        page.screenshot(path=str(ROOT / "review-05-narrow.png"), full_page=True)
        assert page.locator("#intake.active").count() == 1
        assert page.locator("#start-processing").is_disabled()
        page.locator("#show-progress").click()
        assert "確認済み" in page.locator("#progress-cards .card").first.inner_text()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        print("Four-screen mock interaction check passed")
        browser.close()


if __name__ == "__main__":
    main()
