import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { renderDeck } from './render.mjs';

const input = JSON.parse(await readFile(new URL('../../../examples/starter-deck.json', import.meta.url), 'utf8'));
const output = new URL('../../../artifacts/starter.pptx', import.meta.url);
await mkdir(new URL('../../../artifacts/', import.meta.url), { recursive: true });
await writeFile(output, await renderDeck(input));
console.log(`Generated ${output.pathname}`);
