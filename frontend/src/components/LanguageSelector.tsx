import { useLanguage, Language } from '../i18n'

export function LanguageSelector() {
  const { language, setLanguage } = useLanguage()

  const languages: { code: Language; flag: string; name: string }[] = [
    { code: 'es', flag: '🇪🇸', name: 'Español' },
    { code: 'en', flag: '🇬🇧', name: 'English' },
  ]

  return (
    <div className="flex items-center gap-1 bg-slate-700/50 rounded-lg p-1">
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => setLanguage(lang.code)}
          className={`
            flex items-center gap-1.5 px-2 py-1 rounded-md text-sm font-medium transition-all
            ${language === lang.code
              ? 'bg-emerald-500/20 text-emerald-400 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-600/50'
            }
          `}
          title={lang.name}
        >
          <span className="text-base">{lang.flag}</span>
          <span className="hidden sm:inline">{lang.code.toUpperCase()}</span>
        </button>
      ))}
    </div>
  )
}


