import { watch } from 'vue'
import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'
import { orderLocales, resolveLocale } from './locale'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const discoveredLocales = []

for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    messages[key] = localeFiles[path].default
    discoveredLocales.push({ key, label: languages[key].label })
  }
}

const availableLocales = orderLocales(discoveredLocales)

const initialLocale = resolveLocale(localStorage.getItem('locale'), Object.keys(messages)) || 'en'

const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'en',
  messages
})

// Keep the browser tab, page description and language in sync with the UI.
watch(i18n.global.locale, (locale) => {
  document.documentElement.lang = locale
  document.title = i18n.global.t('meta.title')
  document.querySelector('meta[name="description"]')?.setAttribute('content', i18n.global.t('meta.description'))
}, { immediate: true })

export { availableLocales }
export default i18n
