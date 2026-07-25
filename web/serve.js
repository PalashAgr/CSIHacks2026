import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const root = path.resolve('dist');
const host = '127.0.0.1';
const port = 5173;

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2'
};

function send(res, statusCode, body, contentType = 'text/plain; charset=utf-8') {
  res.writeHead(statusCode, { 'Content-Type': contentType });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const requestUrl = url.parse(req.url || '/');
  const pathname = decodeURIComponent(requestUrl.pathname || '/');
  const cleaned = pathname === '/' ? '/index.html' : pathname;
  const filePath = path.join(root, cleaned);

  if (!filePath.startsWith(root)) {
    send(res, 403, 'Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      const fallback = path.join(root, 'index.html');
      fs.readFile(fallback, (fallbackErr, fallbackData) => {
        if (fallbackErr) {
          send(res, 500, 'Build output not found. Run `npm run build` first.');
          return;
        }

        send(res, 200, fallbackData, 'text/html; charset=utf-8');
      });
      return;
    }

    const type = mimeTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
    send(res, 200, data, type);
  });
});

server.listen(port, host, () => {
  console.log(`Local site running at http://${host}:${port}`);
});
