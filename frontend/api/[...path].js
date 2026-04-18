function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || '').replace(/\/+$/, '')
}

function buildTargetUrl(baseUrl, pathSegments, query) {
  const target = new URL(`${normalizeBaseUrl(baseUrl)}/${pathSegments.join('/')}`)

  for (const [key, value] of Object.entries(query)) {
    if (key === 'path' || value == null) continue

    if (Array.isArray(value)) {
      for (const item of value) {
        target.searchParams.append(key, String(item))
      }
      continue
    }

    target.searchParams.set(key, String(value))
  }

  return target
}

function buildHeaders(headers) {
  const passthrough = {}

  for (const [key, value] of Object.entries(headers || {})) {
    const lower = key.toLowerCase()
    if (['host', 'connection', 'content-length'].includes(lower)) continue
    if (typeof value === 'undefined') continue
    passthrough[key] = value
  }

  return passthrough
}

export default async function handler(req, res) {
  const baseUrl = process.env.API_BASE_URL || process.env.VITE_API_URL

  if (!baseUrl) {
    res.status(500).json({
      detail: 'API proxy is not configured. Set API_BASE_URL in the Vercel project.',
    })
    return
  }

  const pathSegments = Array.isArray(req.query.path)
    ? req.query.path
    : req.query.path
    ? [req.query.path]
    : []

  const targetUrl = buildTargetUrl(baseUrl, pathSegments, req.query)
  const init = {
    method: req.method,
    headers: buildHeaders(req.headers),
  }

  if (!['GET', 'HEAD'].includes(req.method || 'GET') && typeof req.body !== 'undefined') {
    init.body =
      typeof req.body === 'string' || Buffer.isBuffer(req.body)
        ? req.body
        : JSON.stringify(req.body)

    if (!init.headers['content-type'] && !init.headers['Content-Type']) {
      init.headers['content-type'] = 'application/json'
    }
  }

  try {
    const response = await fetch(targetUrl, init)
    const text = await response.text()

    res.status(response.status)

    response.headers.forEach((value, key) => {
      if (['content-length', 'transfer-encoding', 'content-encoding'].includes(key.toLowerCase())) {
        return
      }
      res.setHeader(key, value)
    })

    res.send(text)
  } catch (error) {
    res.status(502).json({
      detail: 'Failed to reach upstream API.',
      error: error instanceof Error ? error.message : 'unknown_error',
      upstream: normalizeBaseUrl(baseUrl),
    })
  }
}
