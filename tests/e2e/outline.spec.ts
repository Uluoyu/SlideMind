import { expect, test, type Page } from '@playwright/test';

async function newDeck(page: Page, name: string, pages: string) {
  await page.goto('/');
  await page.getByRole('button', { name: '创建项目', exact: true }).click();
  await page.getByLabel('项目名称').fill(name);
  await page.locator('form').getByRole('button', { name: '创建项目', exact: true }).click();
  await page.getByRole('button', { name: '新建 PPT', exact: true }).click();
  await page.getByLabel('汇报主题').fill(`${name}汇报`);
  await page.getByLabel('页数', { exact: true }).fill(pages);
  await page.getByRole('button', { name: '创建 PPT 任务' }).click();
}

test('merge, split and confirm a local outline', async ({ page }) => {
  await newDeck(page, '大纲编辑', '4');
  await page.getByRole('button', { name: '生成初始大纲' }).click();
  await expect(page.getByText('未配置模型服务')).toBeVisible();
  // Local planner offers no feedback revision.
  await expect(page.getByLabel('修改意见')).toHaveCount(0);
  await page.getByLabel('第 2 页标题').fill('技术架构');
  await page.getByLabel('第 3 页标题').fill('人员轨迹');
  await page.getByRole('button', { name: '合并第 2 页与下一页' }).click();
  await expect(page.getByLabel('第 2 页标题')).toHaveValue('技术架构与人员轨迹');
  await expect(page.getByLabel('第 4 页标题')).toHaveCount(0);
  await page.getByRole('button', { name: '拆分第 2 页' }).click();
  await expect(page.getByLabel('第 3 页标题')).toHaveValue('技术架构与人员轨迹（续）');
  await page.getByLabel('第 3 页标题').fill('AI 违规检测');
  await page.getByRole('button', { name: '确认并保存大纲' }).click();
  await expect(page.getByText(/查看已确认大纲/)).toBeVisible();
  await page.reload();
  await page.getByText('查看已确认大纲（4 页）').click();
  await expect(page.getByLabel('第 3 页标题')).toHaveValue('AI 违规检测');
});

test('model outline shows sources, revises by feedback and confirms', async ({ page }) => {
  // The e2e API runs the local planner; decorate its real responses as a model outline so the
  // UI paths run while the server still owns state and validates the final confirm.
  const source = { chunkId: 0, documentId: 0, fileName: '方案.docx', pageNo: 2, location: '第 2 页', excerpt: '人员轨迹定位精度达到 1 米。' };
  let revision: { feedback: string; pages: { pageNo: number; title: string; sourceChunkIds: number[] }[] } | null = null;
  await page.route('**/outline/generate?*', async route => {
    const body = route.request().postData();
    if (body) {
      revision = JSON.parse(body);
      // Local planner rejects feedback; answer as the model would, from the edited outline.
      const pages = revision!.pages.slice(0, 2).map((p, i) => ({ ...p, pageNo: i + 1, purpose: '按意见调整', sourceChunkIds: [], sources: [] }));
      pages.push({ pageNo: 3, title: 'AI 违规检测', purpose: '新增页面', sourceChunkIds: [], sources: [] });
      return route.fulfill({ json: { status: 'OUTLINE_GENERATED', planner: 'model', warning: null, pages } });
    }
    const response = await route.fetch();
    const outline = await response.json();
    outline.planner = 'model';
    outline.warning = '资料检索暂不可用，大纲仅依据需求生成；可稍后重新生成。';
    outline.pages[0] = { ...outline.pages[0], sourceChunkIds: [source.chunkId], sources: [source] };
    await route.fulfill({ response, json: outline });
  });
  await newDeck(page, '模型大纲', '3');
  await page.getByRole('button', { name: '生成初始大纲' }).click();
  await expect(page.getByText('由模型结合项目资料生成')).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: '资料检索暂不可用' })).toBeVisible();
  await page.getByText('依据 1 条项目资料').click();
  await expect(page.getByText('人员轨迹定位精度达到 1 米。')).toBeVisible();
  await page.getByLabel('第 1 页标题').fill('项目背景');
  await page.getByLabel('修改意见').fill('增加一页 AI 违规检测');
  await page.getByRole('button', { name: '按意见调整大纲' }).click();
  await expect(page.getByLabel('第 3 页标题')).toHaveValue('AI 违规检测');
  expect(revision!.feedback).toBe('增加一页 AI 违规检测');
  expect(revision!.pages[0]).toMatchObject({ pageNo: 1, title: '项目背景', sourceChunkIds: [0] });
  expect(Object.keys(revision!.pages[0]).sort()).toEqual(['pageNo', 'purpose', 'sourceChunkIds', 'title']);
  await page.getByRole('button', { name: '确认并保存大纲' }).click();
  await expect(page.getByText(/查看已确认大纲/)).toBeVisible();
});

test('removing a cited source drops it from the confirm payload', async ({ page }) => {
  const source = { chunkId: 424242, documentId: 1, fileName: '伪造.docx', pageNo: null, location: '片段 1', excerpt: '不存在的资料' };
  await page.route('**/outline/generate?*', async route => {
    const response = await route.fetch();
    const outline = await response.json();
    outline.planner = 'model';
    outline.pages[0] = { ...outline.pages[0], sourceChunkIds: [source.chunkId], sources: [source] };
    await route.fulfill({ response, json: outline });
  });
  await newDeck(page, '来源校验', '2');
  await page.getByRole('button', { name: '生成初始大纲' }).click();
  // The server rejects ids it cannot resolve for this project.
  await page.getByRole('button', { name: '确认并保存大纲' }).click();
  await expect(page.getByRole('alert')).toContainText('大纲引用了当前项目之外');
  await page.getByText('依据 1 条项目资料').click();
  await page.getByRole('button', { name: /移除第 1 页引用/ }).click();
  await expect(page.getByText('依据 1 条项目资料')).toHaveCount(0);
  await page.getByRole('button', { name: '确认并保存大纲' }).click();
  await expect(page.getByText(/查看已确认大纲/)).toBeVisible();
});
