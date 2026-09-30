import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import JSZip from 'jszip';

test('create, confirm, edit, render, download and reopen a presentation', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '创建项目', exact: true }).click();
  await page.getByLabel('项目名称').fill('浏览器验收项目');
  await page.locator('form').getByRole('button', { name: '创建项目', exact: true }).click();
  await page.getByRole('button', { name: '新建 PPT', exact: true }).click();
  await page.getByLabel('汇报主题').fill('基础框架验收');
  await page.getByLabel('页数', { exact: true }).fill('3');
  await page.getByRole('button', { name: '创建 PPT 任务' }).click();
  await page.getByRole('button', { name: '生成初始大纲' }).click();
  await page.getByLabel('第 2 页标题').fill('项目进展');
  await page.getByRole('button', { name: '确认并保存大纲' }).click();
  await page.getByRole('button', { name: '生成页面草稿' }).click();
  await page.getByRole('button', { name: '编辑第 2 页' }).click();
  await page.getByLabel('页面标题', { exact: true }).fill('已核实的项目进展');
  await page.getByRole('textbox', { name: '正文 1', exact: true }).fill('项目已完成基础框架搭建。');
  await expect(page.getByRole('button', { name: '生成 PPTX', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '保存当前页' }).click();
  await page.getByRole('button', { name: '生成 PPTX', exact: true }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 PPTX', exact: true }).click();
  const download = await downloaded;
  const path = await download.path();
  const pptx = await readFile(path!);
  expect(pptx.subarray(0, 2).toString()).toBe('PK');
  const archive = await JSZip.loadAsync(pptx);
  expect(Object.keys(archive.files).filter(name => /^ppt\/slides\/slide\d+\.xml$/.test(name))).toHaveLength(3);
  expect(await archive.file('ppt/slides/slide2.xml')!.async('string')).toContain('已核实的项目进展');
  await page.reload();
  await page.getByRole('button', { name: '编辑第 2 页' }).click();
  await expect(page.getByLabel('页面标题', { exact: true })).toHaveValue('已核实的项目进展');
  await expect(page.getByRole('button', { name: '下载 PPTX', exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: '正文 1', exact: true }).fill('修改后的内容');
  await page.getByRole('button', { name: '保存当前页' }).click();
  await expect(page.getByRole('button', { name: '下载 PPTX', exact: true })).toHaveCount(0);
  await page.screenshot({ path: 'artifacts/workspace-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'artifacts/workspace-mobile.png', fullPage: true });
});

test('failed re-export refreshes server status and allows retry', async ({ page, request }) => {
  const project = await (await request.post('/api/ppt/projects', { data: { name: '失败重试测试' } })).json();
  const deck = await (await request.post('/api/ppt/documents', {
    data: { projectId: project.id, title: '失败恢复', pageCount: 1 },
  })).json();
  const base = `/api/ppt/documents/${deck.id}`;
  const scope = `?projectId=${project.id}`;
  const outline = await (await request.post(`${base}/outline/generate${scope}`)).json();
  await request.post(`${base}/outline/confirm${scope}`, { data: { pages: outline.pages } });
  await request.post(`${base}/pages/generate${scope}`);
  expect((await request.post(`${base}/render${scope}`)).ok()).toBe(true);
  await page.goto('/');
  await expect(page.getByRole('button', { name: '下载 PPTX', exact: true })).toBeVisible();
  // The API failure contract is covered by test_pages.py; here simulate its HTTP responses.
  await page.route(`**${base}/render${scope}`, route => route.fulfill({
    status: 503, json: { detail: '渲染服务暂不可用' },
  }), { times: 1 });
  await page.route(`**${base}${scope}`, async route => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), status: 'FAILED' } });
  }, { times: 1 });
  await page.getByRole('button', { name: '生成 PPTX', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('渲染服务暂不可用');
  await expect(page.getByRole('button', { name: '下载 PPTX', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '生成 PPTX', exact: true }).click();
  await expect(page.getByRole('button', { name: '下载 PPTX', exact: true })).toBeVisible();
});
