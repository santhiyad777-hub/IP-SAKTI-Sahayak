"""Real browser registration/login/logout/export checks against isolated port 8503."""
import json
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def main():
    suffix=uuid.uuid4().hex[:8];password='a browser test passphrase 12345'
    results={}
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(accept_downloads=True)
        page=context.new_page();page.goto('http://127.0.0.1:8503');page.wait_for_timeout(1500)
        expect(page.get_by_role('heading',name='IP-SAKTI Sahayak')).to_be_visible(timeout=60000)
        results['unauthenticated_chat_hidden']=page.get_by_placeholder('Ask about Ayurveda IP, classification, ABS or export requirements...').count()==0
        for index in (1,2):
            user=f'browser_{suffix}_{index}'
            page.get_by_role('tab',name='Create account',exact=True).click()
            page.get_by_label('Choose a username',exact=True).fill(user)
            page.get_by_label('Choose a password',exact=True).fill(password)
            page.get_by_label('Confirm password',exact=True).fill(password)
            page.get_by_text('I understand that questions and relevant document excerpts are sent to the configured AI/translation providers. My workspace is stored on this service.',exact=True).click()
            page.get_by_role('button',name='Create account',exact=True).click()
            expect(page.get_by_text('Account created. Use the Sign in tab to continue.')).to_be_visible(timeout=30000)
            page.get_by_role('tab',name='Sign in',exact=True).click()
            page.get_by_label('Username',exact=True).fill(user)
            page.get_by_label('Password',exact=True).fill(password)
            page.get_by_role('button',name='Sign in',exact=True).click()
            expect(page.get_by_role('button',name='Sign out',exact=True)).to_be_visible(timeout=60000)
            expect(page.get_by_text('Signed in as '+user)).to_be_visible()
            results[f'register_login_{index}']=True
            if index==1:
                # Classification intake is deterministic and makes no provider request.
                entry=page.get_by_placeholder('Ask about Ayurveda IP, classification, ABS or export requirements...')
                entry.fill('En herbal product medicine-aa, food-aa, cosmetic-aa?');entry.press('Enter')
                expect(page.get_by_text('En herbal product medicine-aa, food-aa, cosmetic-aa?',exact=True).first).to_be_visible(timeout=30000)
                page.get_by_role('button',name='Workspace exports',exact=True).click()
                link=page.locator('a.private-download').filter(has_text='TXT').first
                expect(link).to_be_visible(timeout=30000)
                results['private_download_has_no_public_url']=link.get_attribute('href').startswith('data:text/plain;base64,')
                with page.expect_download() as event:link.click()
                download=event.value
                text=Path(download.path()).read_text(encoding='utf-8')
                results['export_contains_own_chat']='En herbal product' in text
            else:
                results['second_user_has_no_first_user_history']='En herbal product medicine-aa, food-aa, cosmetic-aa?' not in page.locator('body').inner_text()
            page.get_by_role('button',name='Sign out',exact=True).click()
            expect(page.get_by_role('heading',name='IP-SAKTI Sahayak')).to_be_visible(timeout=30000)
            expect(page.locator('a.private-download')).to_have_count(0,timeout=30000)
            results[f'logout_clears_workspace_{index}']=True
        # File storage cannot be fetched as a static asset.
        response=context.request.get('http://127.0.0.1:8503/app/static/../.security-test-browser/accounts.sqlite3')
        results['database_not_served']=b'SQLite format' not in response.body()
        browser.close()
    Path('evaluation/security_browser_results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2));assert all(results.values())

if __name__=='__main__':main()
