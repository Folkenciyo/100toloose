import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Info, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLanguage } from '../i18n'

interface InfoTooltipProps {
  title: string
  description: string
  example: string
}

export function InfoTooltip({ title, description, example }: InfoTooltipProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { t } = useLanguage()

  const modalContent = (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/80 z-[9998]"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-4 md:inset-8 lg:inset-16 z-[9999] bg-cyber-surface border border-cyber-border rounded-xl shadow-2xl overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-cyber-border bg-cyber-card">
              <h3 className="text-xl font-bold text-cyber-primary">{title}</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="p-2 rounded-lg hover:bg-cyber-danger/20 text-cyber-muted hover:text-cyber-danger transition-all"
              >
                <X size={24} />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              <div className="max-w-4xl mx-auto space-y-6">
                {/* Description */}
                <div>
                  <h4 className="text-sm font-semibold text-cyber-muted mb-3 uppercase tracking-wide">
                    Descripción
                  </h4>
                  <p className="text-base text-cyber-text leading-relaxed">
                    {description}
                  </p>
                </div>

                {/* Example */}
                <div className="bg-cyber-card rounded-lg p-6 border border-cyber-border">
                  <h4 className="text-sm font-semibold text-cyber-primary mb-3 uppercase tracking-wide">
                    {t.common.example}
                  </h4>
                  <p className="text-base text-cyber-text leading-relaxed">
                    {example}
                  </p>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-cyber-border bg-cyber-card">
              <button
                onClick={() => setIsOpen(false)}
                className="w-full md:w-auto px-8 py-3 bg-cyber-primary text-cyber-bg rounded-lg font-semibold hover:opacity-90 transition-all"
              >
                {t.common.close}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )

  return (
    <>
      <button
        type="button"
        className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-cyber-primary/20 text-cyber-primary hover:bg-cyber-primary/30 transition-all ml-2"
        onClick={(e) => {
          e.stopPropagation()
          setIsOpen(true)
        }}
        title="Ver información"
      >
        <Info size={14} />
      </button>
      {typeof window !== 'undefined' && createPortal(modalContent, document.body)}
    </>
  )
}

