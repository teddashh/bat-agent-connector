// Capture the real shared frontend with synthetic data, never live host credentials.
// Start desktop/tests/static-server.mjs with BATC_UI_TEST_PORT=18746 first.
import { chromium } from '../desktop/node_modules/@playwright/test/index.mjs';
import { attentionFixture, mountAttention } from '../desktop/tests/attention-fixture.ts';
import { publishedFixture, dispatchProject, selected } from '../desktop/tests/repository-start-fixture.ts';
import { mkdir } from 'node:fs/promises';
const output = new URL('../site/images/', import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
try {
  for (const [language, locale] of [['en', 'en-US'], ['zh', 'zh-TW']]) {
    const context = await browser.newContext({ locale, viewport: { width: 1240, height: 820 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const fixture = attentionFixture();
    fixture.data.items[0].title = language === 'zh' ? '審閱搜尋功能的測試與成果' : 'Review search results and tests';
    fixture.data.sessions[0].title = language === 'zh' ? '搜尋功能：確認空結果的呈現方式' : 'Search: confirm the empty-results behavior';
    await mountAttention(page, false, fixture);
    await page.goto('http://127.0.0.1:18746/dashboard/#/');
    await page.getByText(fixture.data.items[0].title, { exact: true }).waitFor();
    await page.screenshot({ path: new URL(`attention-${language}.png`, output).pathname });
    const composer = await context.newPage();
    composer.on('pageerror', error => errors.push(error.message));
    await publishedFixture(composer, false, { dispatch: true, scopes: ['observe', 'start', 'manage'],
      project: { project_id: dispatchProject, name: language === 'zh' ? '文件搜尋' : 'Documentation search',
        description: language === 'zh' ? '讓讀者更快找到需要的文件。' : 'Help readers find the right documentation.',
        repositories: ['example/project'], version: 1, archived: false, counts: { total: 0, approved: 0 } } });
    await composer.goto('http://127.0.0.1:18746/dashboard/#/project/' + dispatchProject);
    await composer.locator('a[href^="#/dispatch/"]').click();
    await composer.locator('[data-published-start]').waitFor();
    await composer.locator('[data-published-start] select').first().selectOption(JSON.stringify(selected));
    await composer.locator('[data-published-start] input').first().fill('main');
    await composer.locator('[data-published-start] textarea').first().fill(language === 'zh'
      ? '改善文件搜尋的空結果提示，補上相關測試，並提供變更摘要供審閱。'
      : 'Improve the empty-results message in documentation search. Add focused tests and provide a change summary for review.');
    await composer.screenshot({ path: new URL(`dispatch-${language}.png`, output).pathname });
    if (errors.length) throw new Error(errors.join('\n'));
    await context.close();
  }
} finally { await browser.close(); }
