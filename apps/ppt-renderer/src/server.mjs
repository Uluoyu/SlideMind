import { createServer } from 'node:http';
import { InvalidDeck, renderDeck } from './render.mjs';

export function createRendererServer() {
  return createServer(async (request, response) => {
    if (request.method === 'GET' && request.url === '/health') {
      response.writeHead(200, { 'Content-Type': 'application/json' });
      return response.end(JSON.stringify({ status: 'ok', service: 'slidemind-renderer' }));
    }
    if (request.method !== 'POST' || request.url !== '/render') {
      response.writeHead(404); return response.end();
    }
    try {
      const chunks = [];
      let size = 0;
      for await (const chunk of request) {
        size += chunk.length;
        if (size > 2 * 1024 * 1024) {
          response.writeHead(413); response.end('Request exceeds 2 MB');
          request.resume(); return;
        }
        chunks.push(chunk);
      }
      const output = await renderDeck(JSON.parse(Buffer.concat(chunks).toString('utf8')));
      response.writeHead(200, {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'Content-Disposition': 'attachment; filename="presentation.pptx"',
      });
      response.end(output);
    } catch (error) {
      const invalid = error instanceof InvalidDeck || error instanceof SyntaxError;
      response.writeHead(invalid ? 422 : 500, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify({ detail: invalid ? error.message : 'PPT rendering failed' }));
      if (!invalid) console.error(error);
    }
  });
}

// Importing this module in tests must not bind a port.
if (process.argv[1] && import.meta.url === (await import('node:url')).pathToFileURL(process.argv[1]).href) {
  const port = Number(process.env.RENDERER_PORT || 3001);
  createRendererServer().listen(port, '127.0.0.1', () => {
    console.log(`SlideMind renderer: http://127.0.0.1:${port}`);
  });
}
