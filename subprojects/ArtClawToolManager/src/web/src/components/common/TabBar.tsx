// Ref: docs/ui/ui-design.md#Skills
// Reusable tab bar component
import { cn } from '../../utils/cn'

interface Tab<T extends string> {
  key: T
  label: string
}

interface TabBarProps<T extends string> {
  tabs: Tab<T>[]
  activeTab: T
  onChange: (tab: T) => void
  className?: string
}

export default function TabBar<T extends string>({
  tabs,
  activeTab,
  onChange,
  className,
}: TabBarProps<T>) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            'px-3 py-1.5 rounded text-small font-medium transition-colors',
            activeTab === tab.key
              ? 'bg-accent text-white'
              : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
