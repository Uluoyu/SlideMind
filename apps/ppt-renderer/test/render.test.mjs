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
  assert.equal(parseDeck({ ...example, title: '  Title  ' }).title, 'Title');
  assert.throws(() => parseDeck({ ...example, title: '   ' }), InvalidDeck);
  assert.throws(() => parseDeck({ ...example, theme: null }), InvalidDeck);
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
