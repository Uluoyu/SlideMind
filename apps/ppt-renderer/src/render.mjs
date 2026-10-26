import { readFileSync } from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';
import PptxGenJS from 'pptxgenjs';

const schema = JSON.parse(readFileSync(new URL('../../../packages/schemas/deck.schema.json', import.meta.url)));
const validate = new Ajv2020({ allErrors: true, useDefaults: true }).compile(schema);

export class InvalidDeck extends Error {}

function normalize(input) {
  if (typeof input === 'string') return input.trim();
  if (Array.isArray(input)) return input.map(normalize);
  if (input && typeof input === 'object') {
    return Object.fromEntries(Object.entries(input).map(([key, value]) => [key, normalize(value)]));
  }
  return input;
}

export function parseDeck(input) {
  const deck = normalize(input);
  if (!validate(deck)) throw new InvalidDeck(JSON.stringify(validate.errors));
  if (deck.pages.some((page, index) => page.page_no !== index + 1)) {
    throw new InvalidDeck('Page numbers must be sequential, starting at 1.');
  }
  return deck;
}

// Font rule (mirrors PPTX majorFont=headings / minorFont=body): page titles,
// subtitles and block titles use theme.title_font_family; block body text and
// the footer use theme.body_font_family.
const MARGIN = 0.65;
const GUTTER = 0.3;

function addHeader(slide, page, theme, slideWidth) {
  slide.addText(page.title, {
    x: MARGIN, y: 0.65, w: slideWidth - MARGIN * 2, h: 0.85,
    fontFace: theme.title_font_family, fontSize: 28, bold: true,
    color: theme.text_color.slice(1), breakLine: false, margin: 0,
  });
  if (page.subtitle) slide.addText(page.subtitle, {
    x: MARGIN, y: 1.6, w: slideWidth - MARGIN * 2, h: 0.7,
    fontFace: theme.title_font_family, fontSize: 16, color: theme.text_color.slice(1), margin: 0,
  });
}

function addContent(slide, page, theme, slideWidth, slideHeight) {
  const columns = page.layout === 'two_column' ? 2 : 1;
  const rows = Math.ceil(page.content.length / columns);
  const width = (slideWidth - 2 * MARGIN - (columns - 1) * GUTTER) / columns;
  // Keep the original 3.8in band on standard heights and clamp it so the content
  // stays above the footer (slideHeight - 0.65) on shorter template slides (e.g. 16:10).
  const band = Math.min(3.8, slideHeight - 1.0 - 2.55);
  const height = (band - Math.max(0, rows - 1) * GUTTER) / Math.max(1, rows);
  for (const [index, block] of page.content.entries()) {
    const x = MARGIN + (index % columns) * (width + GUTTER);
    const y = 2.55 + Math.floor(index / columns) * (height + GUTTER);
    // On very short rows the fixed 0.45in title would starve the body; shrink both instead.
    const titleHeight = height >= 0.65 ? 0.45 : Math.max(0.2, height * 0.45);
    const bodyOffset = titleHeight + 0.1;
    slide.addText(block.title, {
      x, y, w: width, h: titleHeight, fontFace: theme.title_font_family, fontSize: 20,
      bold: true, color: theme.primary_color.slice(1), margin: 0,
    });
    slide.addText(block.text, {
      x, y: y + bodyOffset, w: width, h: Math.max(0.15, height - bodyOffset),
      fontFace: theme.body_font_family, fontSize: 17, color: theme.text_color.slice(1),
      margin: 0, valign: 'top', fit: 'shrink',
    });
  }
}

export async function renderDeck(input) {
  const deck = parseDeck(input);
  const { width: WIDTH, height: HEIGHT } = deck.slide_size;
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'SLIDEMIND', width: WIDTH, height: HEIGHT });
  pptx.layout = 'SLIDEMIND';
  pptx.author = 'SlideMind';
  pptx.subject = 'Page JSON renderer';
  pptx.title = deck.title;
  pptx.lang = 'zh-CN';
  for (const page of deck.pages) {
    const slide = pptx.addSlide();
    slide.background = { color: deck.theme.background_color.slice(1) };
    addHeader(slide, page, deck.theme, WIDTH);
    addContent(slide, page, deck.theme, WIDTH, HEIGHT);
    slide.addText(`${deck.theme.footer}  /  ${String(page.page_no).padStart(2, '0')}`, {
      x: MARGIN, y: HEIGHT - 0.65, w: WIDTH - MARGIN * 2, h: 0.25,
      fontFace: deck.theme.body_font_family, fontSize: 11, color: deck.theme.primary_color.slice(1),
      margin: 0,
    });
    const notes = page.content.flatMap(block => block.sources.map(source =>
      `${source.file_name} (document=${source.document_id}, page=${source.page_no ?? 'N/A'}): ${source.excerpt}`));
    if (notes.length) slide.addNotes(notes.join('\n'));
  }
  return pptx.write({ outputType: 'nodebuffer', compression: true });
}
