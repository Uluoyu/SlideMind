import { expect, test } from '@playwright/test';

test('uploaded project text becomes searchable with a readable source', async ({ page, request }) => {
  test.setTimeout(120_000);
  const projectResponse = await request.post('/api/ppt/projects', { data: { name: '资料检索验收' } });
  expect(projectResponse.ok()).toBe(true);
  await page.goto('/');
  await page.getByRole('button', { name: '资料检索验收', exact: true }).click();
  await page.getByRole('button', { name: '资料与模板', exact: true }).click();

  await expect(page.getByRole('button', { name: '选择文件', exact: true })).toBeEnabled();
  const content = '晨星项目交付记录\n晨星项目采用蓝鹭方案，验收口令为青石桥。\n项目于九月完成数据归档，负责人为林舟。';
  await page.locator('input[type=file]').setInputFiles({
    name: '晨星项目记录.txt', mimeType: 'text/plain', buffer: Buffer.from(content, 'utf8'),
  });
  const file = page.getByRole('listitem').filter({ hasText: '晨星项目记录.txt' });
  await expect(file).toContainText('可检索', { timeout: 90_000 });
  await expect(file).toContainText(/\d+ 个片段/);
  await page.getByRole('textbox', { name: '搜索项目资料' }).fill('晨星项目的验收口令是什么');
  await page.getByRole('button', { name: '搜索资料', exact: true }).click();
  const result = page.getByRole('article').filter({ hasText: '晨星项目记录.txt' }).first();
  await expect(result).toContainText('青石桥');
  await result.getByRole('button', { name: '查看来源' }).click();
  const source = page.getByRole('region', { name: '来源详情' });
  await expect(source).toContainText('晨星项目记录.txt');
  await expect(source).toContainText('负责人为林舟');
  await expect(source).toContainText('青石桥');
  await page.screenshot({ path: 'artifacts/library-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'artifacts/library-mobile.png', fullPage: true });
  await source.getByRole('button', { name: '关闭来源详情' }).click();
  await expect(source).toHaveCount(0);
  await expect(result.getByRole('button', { name: '查看来源' })).toBeFocused();
  await result.getByRole('button', { name: '查看来源' }).click();

  // Asset/template libraries must not imply that their uploads are parsed or searchable.
  await page.getByRole('button', { name: '图片素材', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '搜索项目资料' })).toHaveCount(0);
  await expect(source).toHaveCount(0);
  await page.getByRole('button', { name: '项目资料', exact: true }).click();
  await expect(file).toContainText('可检索');
  await expect(page.getByRole('article')).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: '搜索项目资料' })).toHaveValue('');
});

test('a corrupt document exposes a clear failure and can be retried', async ({ page, request }) => {
  test.setTimeout(120_000);
  const projectResponse = await request.post('/api/ppt/projects', { data: { name: '资料失败恢复' } });
  expect(projectResponse.ok()).toBe(true);
  await page.goto('/');
  await page.getByRole('button', { name: '资料失败恢复', exact: true }).click();
  await page.getByRole('button', { name: '资料与模板', exact: true }).click();
  await expect(page.getByRole('button', { name: '选择文件', exact: true })).toBeEnabled();
  const uploaded = page.waitForResponse(response => response.url().endsWith('/documents') && response.request().method() === 'POST');
  await page.locator('input[type=file]').setInputFiles({
    name: '损坏的项目资料.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.7\nnot a valid PDF'),
  });
  const uploadResponse = await uploaded;
  expect(uploadResponse.ok()).toBe(true);
  const document = await uploadResponse.json();
  const file = page.getByRole('listitem').filter({ hasText: '损坏的项目资料.pdf' });
  await expect(file).toContainText('处理失败', { timeout: 90_000 });
  await expect(file.getByRole('alert')).not.toBeEmpty();
  const retried = page.waitForResponse(response => response.url().endsWith(`/documents/${document.id}/process`));
  await file.getByRole('button', { name: '重试处理' }).click();
  expect((await retried).status()).toBe(202);
  await expect(file).toContainText('处理失败', { timeout: 90_000 });
  await expect(file.getByRole('alert')).not.toBeEmpty();
  await expect(file.getByRole('button', { name: '重试处理' })).toBeEnabled();
});
