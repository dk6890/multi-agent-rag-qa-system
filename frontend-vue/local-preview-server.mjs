import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer, request as proxyRequest } from 'node:http'
import { extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const distDir = join(__dirname, 'dist')
const host = '127.0.0.1'
const port = Number(process.env.FRONTEND_PORT || 5173)
const backendHost = process.env.BACKEND_HOST || '127.0.0.1'
const backendPort = Number(process.env.BACKEND_PORT || 8080)

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon'
}

function proxyApi(req, res) {
  const options = {
    hostname: backendHost,
    port: backendPort,
    path: req.url,
    method: req.method,
    headers: {
      ...req.headers,
      host: `${backendHost}:${backendPort}`
    }
  }

  const upstream = proxyRequest(options, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers)
    upstreamRes.pipe(res)
  })

  upstream.on('error', (error) => {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({ code: 502, msg: `Backend unavailable: ${error.message}`, data: null }))
  })

  req.pipe(upstream)
}

function serveStatic(req, res) {
  const rawPath = decodeURIComponent((req.url || '/').split('?')[0])
  const requestedPath = rawPath === '/' ? '/index.html' : rawPath
  const filePath = normalize(join(distDir, requestedPath))

  if (!filePath.startsWith(distDir)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }

  const pathToServe = existsSync(filePath) && statSync(filePath).isFile()
    ? filePath
    : join(distDir, 'index.html')

  const ext = extname(pathToServe)
  res.writeHead(200, { 'Content-Type': contentTypes[ext] || 'application/octet-stream' })
  createReadStream(pathToServe).pipe(res)
}

createServer((req, res) => {
  if ((req.url || '').startsWith('/api/')) {
    proxyApi(req, res)
    return
  }
  serveStatic(req, res)
}).listen(port, host, () => {
  console.log(`Frontend preview on http://${host}:${port}`)
  console.log(`Proxying /api to http://${backendHost}:${backendPort}`)
})
