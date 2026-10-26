import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import JSZip from 'jszip';
import { InvalidDeck, parseDeck, renderDeck } from '../src/render.mjs';
import { createRendererServer } from '../src/server.mjs';

const example = JSON.parse(await readFile(new URL('../../../examples/starter-deck.json', import.meta.url), 'utf8'));

test('renders editable slides with shared theme and source notes', async () => {
  const deck = structuredClone(example);
  deck.pages[1].content[0].sources = [{ document_id: 1, file_name: 'report.md', page_no: 2, excerpt: 'Original evidence' }];
  const zip = await JSZip.loadAsync(await renderDeck(deck));
  assert.equal(Object.keys(zip.files).filter(path => /^ppt\/slides\/slide\d+\.xml$/.test(path)).length, 2);
  const page = await zip.file('ppt/slides/slide1.xml').async('string');
  assert.match(page, /让想法/);
  assert.match(page, /315C4E/);
  assert.match(await zip.file('ppt/notesSlides/notesSlide2.xml').async('string'), /Original evidence/);
});

test('rejects unsupported layouts, invalid theme and nonsequential pages', () => {
  assert.throws(() => parseDeck({ title: 'x', pages: [{ page_no: 1, title: 'x', layout: 'anything' }] }), InvalidDeck);
  assert.throws(() => parseDeck({ ...example, theme: { primary_color: 'red' } }), InvalidDeck);
  assert.throws(() => parseDeck({ ...example, pages: [{ ...example.pages[0], page_no: 2 }] }), InvalidDeck);
  assert.throws(() => parseDeck({ ...example, pages: [] }), InvalidDeck);
  assert.equal(example.theme, undefined, 'default validation must not mutate the caller');
});

test('normalizes missing defaults and rejects whitespace like the Python contract', () => {
  const parsed = parseDeck(example);
  assert.equal(parsed.theme.primary_color, '#315C4E');
  assert.deepEqual(parseDeck({ title: 'Minimal', pages: [
    { page_no: 1, title: 'Minimal', layout: 'title' },
  ] }).pages[0].content, []);
  assert.deepEqual(parsed.pages[0].content[0].sources, []);
  assert.deepEqual(parsed.slide_size, { width: 13.3333, height: 7.5 });
  assert.equal(parsed.theme.title_font_family, 'Microsoft YaHei');
  assert.deepEqual(parseDeck({ ...example, slide_size: { width: 10 } }).slide_size, { width: 10, height: 7.5 });
  assert.equal(parseDeck({ ...example, title: '  Title  ' }).title, 'Title');
  assert.throws(() => parseDeck({ ...example, title: '   ' }), InvalidDeck);
  assert.throws(() => parseDeck({ ...example, theme: null }), InvalidDeck);
});

test('rejects stale theme.font_family and out-of-bounds slide size', () => {
  assert.throws(() => parseDeck({ ...example, theme: { font_family: 'X' } }), InvalidDeck);
  assert.throws(() => parseDeck({ ...example, slide_size: { width: 100 } }), InvalidDeck);
});

test('applies theme title/body fonts and custom slide size', async () => {
  const deck = {
    title: '公司模板',
    theme: { name: '公司模板', primary_color: '#2E74B5', background_color: '#FFFFFF', text_color: '#1F1F1F', title_font_family: 'SimHei', body_font_family: 'KaiTi', footer: '公司' },
    slide_size: { width: 10, height: 7.5 },
    pages: [
      { page_no: 1, layout: 'title', title: '标题页', subtitle: '副标题', content: [{ title: '要点', text: '正文内容' }] },
    ],
  };
  const zip = await JSZip.loadAsync(await renderDeck(deck));
  const slide = await zip.file('ppt/slides/slide1.xml').async('string');
  const runOf = text => slide.split('</a:r>').find(chunk => chunk.includes(text));
  assert.match(runOf('标题页'), /typeface="SimHei"/); // page title
  assert.match(runOf('副标题'), /typeface="SimHei"/); // subtitle
  assert.match(runOf('要点'), /typeface="SimHei"/); // block title
  assert.match(runOf('正文内容'), /typeface="KaiTi"/); // block body
  assert.match(runOf('公司  /  01'), /typeface="KaiTi"/); // footer follows body font
  assert.match(slide, /srgbClr val="2E74B5"/);
  const presentation = await zip.file('ppt/presentation.xml').async('string');
  assert.match(presentation, /cx="9144000"/); // 10in * 914400 EMU/in
  assert.match(presentation, /cy="6858000"/); // 7.5in * 914400
});

test('defaults slide size to 13.3333 x 7.5 inches', async () => {
  const zip = await JSZip.loadAsync(await renderDeck(structuredClone(example)));
  const presentation = await zip.file('ppt/presentation.xml').async('string');
  assert.match(presentation, new RegExp(`cx="${Math.round(13.3333 * 914400)}"`));
  assert.match(presentation, new RegExp(`cy="${Math.round(7.5 * 914400)}"`));
});

test('footer and block body use the default body font family', async () => {
  const zip = await JSZip.loadAsync(await renderDeck(structuredClone(example)));
  const slide = await zip.file('ppt/slides/slide1.xml').async('string');
  const runOf = text => slide.split('</a:r>').find(chunk => chunk.includes(text));
  assert.match(runOf('SlideMind  /  01'), /typeface="Microsoft YaHei"/);
  assert.match(runOf('本示例用于验证'), /typeface="Microsoft YaHei"/);
});

test('content band stays inside short (16:10) template slides', async () => {
  const deck = {
    title: '短版面',
    slide_size: { width: 10, height: 6.25 },
    pages: [{
      page_no: 1, layout: 'title', title: '标题', subtitle: '副标题',
      content: [1, 2, 3, 4].map(no => ({ title: `要点${no}`, text: `正文内容${no}` })),
    }],
  };
  const zip = await JSZip.loadAsync(await renderDeck(deck));
  assert.match(await zip.file('ppt/presentation.xml').async('string'), /cy="5715000"/); // 6.25in
  const slide = await zip.file('ppt/slides/slide1.xml').async('string');
  const shapes = [...slide.matchAll(/<a:off x="(-?\d+)" y="(-?\d+)"\/><a:ext cx="(\d+)" cy="(\d+)"\/>/g)];
  assert.ok(shapes.length >= 6, `expected text-box shapes, found ${shapes.length}`);
  for (const [, x, y, cx, cy] of shapes) {
    assert.ok(+y + +cy <= 5715000, `shape exceeds 6.25in height: y=${y} cy=${cy}`);
    assert.ok(+x + +cx <= 9144000, `shape exceeds 10in width: x=${x} cx=${cx}`);
  }
});

test('HTTP renderer returns PPTX and rejects malformed input', async t => {
  const server = createRendererServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(`${base}/health`)).status, 200);
  assert.equal((await fetch(`${base}/render`, { method: 'POST', body: '{bad' })).status, 422);
  const response = await fetch(`${base}/render`, { method: 'POST', body: JSON.stringify(example) });
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /presentationml/);
  assert.equal(Buffer.from(await response.arrayBuffer()).subarray(0, 2).toString(), 'PK');
});
