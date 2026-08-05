import axios from 'axios'

const api = axios.create({ baseURL: '/api', withCredentials: true })

// No request interceptor needed — HttpOnly cookies are sent automatically by the browser

let refreshing = null
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401 && !err.config._retry && !err.config._skipRetry) {
      err.config._retry = true
      if (!refreshing) {
        refreshing = axios
          .post('/api/auth/token/refresh/', {}, { withCredentials: true })
          .then(() => true)
          .catch(() => {
            if (window.location.pathname !== '/login') {
              window.location.href = '/login'
            }
            return false
          })
          .finally(() => { refreshing = null })
      }
      const ok = await refreshing
      if (ok) return api.request(err.config)
    }
    return Promise.reject(err)
  }
)

// Carga TODAS las páginas de un endpoint DRF paginado ({count, next, results})
// y devuelve el array completo, para que la UI no se quede con solo la 1ª página
// (25 elementos). Si el endpoint ya devuelve un array (no paginado), lo devuelve
// tal cual. Evita el truncado silencioso a medida que los datos se acumulan.
export async function fetchAll(url, params = {}) {
  const first = await api.get(url, { params: { ...params, page: 1 } })
  const d = first.data
  if (Array.isArray(d)) return d
  if (!d || !('results' in d)) return d
  const items = [...d.results]
  const total = typeof d.count === 'number' ? d.count : items.length
  let page = 2
  while (items.length < total) {
    const r = await api.get(url, { params: { ...params, page } })
    const res = r.data?.results
    if (!res || res.length === 0) break
    items.push(...res)
    page += 1
  }
  return items
}

export default api
