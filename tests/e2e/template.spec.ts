import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import JSZip from 'jszip';

const P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main';
const A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main';

// 10in x 7.5in slide, accent1 2E74B5, dk1/lt1 via sysClr lastClr, major/minor ea fonts.
async function buildTemplatePptx(): Promise<Buffer> {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>');
  zip.file('ppt/presentation.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="${P_NS}" xmlns:a="${A_NS}"><p:sldSz cx="9144000" cy="6858000"/></p:presentation>`);
  zip.file('ppt/theme/theme1.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="${A_NS}" name="验收主题"><a:themeElements>
<a:clrScheme name="验收配色">
<a:dk1><a:sysClr val="windowText" lastClr="1A1A1A"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="3B3B3B"/></a:dk2>
<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
<a:accent1><a:srgbClr val="2E74B5"/></a:accent1>
<a:accent2><a:srgbClr val="4472C4"/></a:accent2>
<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>
<a:accent4><a:srgbClr val="FFC000"/></a:accent4>
<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>
<a:accent6><a:srgbClr val="70AD47"/></a:accent6>
</a:clrScheme>
<a:fontScheme name="验收字体">
<a:majorFont><a:latin typeface="Arial"/><a:ea typeface="验收标题字体"/></a:majorFont>
<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface="验收正文字体"/></a:minorFont>
</a:fontScheme>
</a:themeElements></a:theme>`);
  zip.file('ppt/slideLayouts/slideLayout1.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="${P_NS}" type="title"><p:cSld name="标题版式"/></p:sldLayout>`);
  zip.file('ppt/slideLayouts/slideLayout2.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="${P_NS}" type="obj"><p:cSld name="内容版式"/></p:sldLayout>`);
  return zip.generateAsync({ type: 'nodebuffer' });
}

test('company template theme is applied to the exported PPTX', async ({ page, request }) => {
  test.setTimeout(120_000);
  await page.goto('/');
  await page.getByRole('button', { name: '资料与模板', exact: true }).click();
  await page.getByRole('button', { name: '公司模板', exact: true }).click();
  await expect(page.getByRole('button', { name: '选择文件', exact: true })).toBeEnabled();
  await page.locator('input[type=file]').setInputFiles({
    name: '公司主题模板.pptx',
    mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    buffer: await buildTemplatePptx(),
  });
  const uploaded = page.getByRole('listitem').filter({ hasText: '公司主题模板.pptx' });
  // Parsing happens synchronously inside the upload request.
  await expect(uploaded).toContainText('可应用', { timeout: 90_000 });

  const templates = await (await request.get('/api/ppt/templates')).json();
  const template = templates.find((item: { fileName: string }) => item.fileName === '公司主题模板.pptx');
  expect(template?.status).toBe('READY');
  const project = await (await request.post('/api/ppt/projects', {
    data: { name: '模板应用验收', templateId: template.id },
  })).json();
  const deck = await (await request.post('/api/ppt/documents', {
    data: { projectId: project.id, title: '模板主题导出', pageCount: 2 },
  })).json();
  const base = `/api/ppt/documents/${deck.id}`;
  const scope = `?projectId=${project.id}`;
  const outline = await (await request.post(`${base}/outline/generate${scope}`)).json();
  await request.post(`${base}/outline/confirm${scope}`, { data: { pages: outline.pages } });
  await request.post(`${base}/pages/generate${scope}`);

  // The page was loaded before this project existed; reload so the sidebar picks it up.
  await page.reload();
  await page.getByRole('button', { name: '模板应用验收', exact: true }).click();
  await expect(page.getByText('导出将应用公司模板「公司主题模板.pptx」的主题')).toBeVisible();
  await page.getByRole('button', { name: '生成 PPTX', exact: true }).click();
  await expect(page.getByText(/应用模板主题「公司主题模板/)).toBeVisible();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 PPTX', exact: true }).click();
  const downloadPath = await (await downloaded).path();
  const pptx = await readFile(downloadPath!);
  const archive = await JSZip.loadAsync(pptx);
  const slide1 = await archive.file('ppt/slides/slide1.xml')!.async('string');
  expect(slide1).toContain('2E74B5');        // accent1 -> primary (block titles, footer)
  expect(slide1).toContain('FFFFFF');        // lt1 -> background
  expect(slide1).toContain('1A1A1A');        // dk1 -> text color
  expect(slide1).toContain('验收标题字体');   // majorFont ea -> title font
  expect(slide1).toContain('验收正文字体');   // minorFont ea -> body font
  const presentation = await archive.file('ppt/presentation.xml')!.async('string');
  expect(presentation).toContain('cx="9144000"');
  expect(presentation).toContain('cy="6858000"');
});

test('a corrupt company template exposes a clear failure and can be retried', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto('/');
  await page.getByRole('button', { name: '资料与模板', exact: true }).click();
  await page.getByRole('button', { name: '公司模板', exact: true }).click();
  await expect(page.getByRole('button', { name: '选择文件', exact: true })).toBeEnabled();
  await page.locator('input[type=file]').setInputFiles({
    name: '损坏的公司模板.pptx',
    mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    buffer: Buffer.from('%PDF-1.7 definitely not a zip'),
  });
  const file = page.getByRole('listitem').filter({ hasText: '损坏的公司模板.pptx' });
  await expect(file).toContainText('解析失败', { timeout: 90_000 });
  await expect(file.getByRole('alert')).not.toBeEmpty();
  const retried = page.waitForResponse(response => response.url().includes('/templates/') && response.url().endsWith('/process'));
  await file.getByRole('button', { name: '重试解析' }).click();
  expect((await retried).status()).toBe(200);
  await expect(file).toContainText('解析失败', { timeout: 90_000 });
  await expect(file.getByRole('button', { name: '重试解析' })).toBeEnabled();
});
