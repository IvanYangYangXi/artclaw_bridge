// Ref: docs/ui/ui-design.md#Skills
// Reusable search bar component
import { Search, X } from 'lucide-react'
import { cn } from '../../utils/cn'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export default function SearchBar({ value, onChange, placeholder = '搜索...', className }: SearchBarProps) {
  return (
    <div className={cn('relative flex items-center', className)}>
      <Search className="absolute left-3 w-4 h-4 text-text-dim pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          'w-full pl-9 pr-8 py-2 rounded',
          'bg-bg-tertiary text-text-primary text-body',
          'border border-border-default',
          'focus:border-accent focus:outline-none',
          'placeholder:text-text-dim',
          'transition-colors',
        )}
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2 p-0.5 rounded hover:bg-bg-quaternary text-text-dim hover:text-text-primary transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}
