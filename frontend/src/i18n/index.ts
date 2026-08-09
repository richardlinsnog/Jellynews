


import { ref, computed } from 'vue'

const _currentLocale = ref('en')

// Inline translations — extend as needed
const messages: Record<string, Record<string, string>> = {
  en: {
    'app.title': 'JellyNews',
    'nav.dashboard': 'Dashboard',
    'nav.news': 'News',
    'nav.channels': 'Channels',
    'nav.jellyfin': 'Jellyfin',
    'nav.templates': 'Templates',
    'nav.subscribers': 'Subscribers',
    'nav.logs': 'Delivery Logs',
    'nav.audit': 'Audit',
    'nav.settings': 'Settings',
  },
  'pt-BR': {
    'app.title': 'JellyNews',
    'nav.dashboard': 'Painel',
    'nav.news': 'Notícias',
    'nav.channels': 'Canais',
    'nav.jellyfin': 'Jellyfin',
    'nav.templates': 'Templates',
    'nav.subscribers': 'Assinantes',
    'nav.logs': 'Logs de Entrega',
    'nav.audit': 'Auditoria',
    'nav.settings': 'Configurações',
  },
}

export function useI18n() {
  const locale = computed(() => _currentLocale.value)

  function t(key: string): string {
    const localeMessages = messages[_currentLocale.value] || messages.en
    return localeMessages[key] ?? messages.en[key] ?? key
  }

  function setLocale(loc: string) {
    _currentLocale.value = loc in messages ? loc : 'en'
  }

  return { locale, t, setLocale }
}
