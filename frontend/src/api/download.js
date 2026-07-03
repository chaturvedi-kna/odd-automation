import api from './client'

/**
 * Authenticated file download. Plain <a href> can't send the
 * Authorization header (the API returns 401 "Not authenticated"),
 * so we fetch the file as a blob through the axios client and
 * trigger a browser download.
 */
export async function downloadFile(path, fallbackName = 'download') {
  const r = await api.get(path, { responseType: 'blob' })

  // Prefer the server-provided filename (Content-Disposition)
  let filename = fallbackName
  const cd = r.headers?.['content-disposition']
  if (cd) {
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd)
    if (m) filename = decodeURIComponent(m[1])
  }

  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
