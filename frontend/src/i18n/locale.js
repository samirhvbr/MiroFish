// Catalog tags are also sent to the backend through Accept-Language.
export function resolveLocale(value, availableLocales) {
  const tag = String(value || '').trim().replaceAll('_', '-').toLowerCase()
  const available = new Map(availableLocales.map(key => [key.toLowerCase(), key]))
  if (available.has(tag)) return available.get(tag)
  if (tag.split('-')[0] === 'pt' && available.has('pt-br')) return available.get('pt-br')
  return available.get(tag.split('-')[0])
}

export function orderLocales(locales) {
  const preferred = ['en', 'zh', 'pt-BR']
  const rank = key => preferred.includes(key) ? preferred.indexOf(key) : preferred.length
  return [...locales].sort((a, b) => rank(a.key) - rank(b.key) || a.key.localeCompare(b.key))
}
