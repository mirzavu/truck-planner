import { AutoComplete } from 'antd'
import { useState, useRef } from 'react'

interface Location {
  display_name: string
  lat: string
  lon: string
}

interface Props {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  required?: boolean
  placeholder?: string
}

export function LocationAutocomplete({ value, onChange, disabled, required, placeholder }: Props) {
  const [options, setOptions] = useState<{ value: string; label: string }[]>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearch = (searchText: string) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    if (!searchText) {
      setOptions([])
      return
    }

    timerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(searchText)}&countrycodes=us,ca`)
        if (res.ok) {
          const data: Location[] = await res.json()
          // Get unique values to prevent react key errors
          const uniqueTails = Array.from(new Set(data.map(item => item.display_name)))
          setOptions(uniqueTails.map(name => ({
            value: name,
            label: name
          })))
        }
      } catch (err) {
        console.error('Failed to fetch addresses:', err)
      }
    }, 600)
  }

  return (
    <AutoComplete
      options={options}
      value={value}
      onChange={onChange}
      onSelect={(val) => onChange(val)}
      onSearch={handleSearch}
      disabled={disabled}
      popupClassName="font-sans text-sm rounded-xl"
      className="mt-1.5 w-full block"
    >
      <input 
        required={required}
        placeholder={placeholder}
        className="w-full rounded-xl border border-[#132a38]/20 px-4 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#d44b2c]/50 transition-all font-sans text-sm text-[#132a38]" 
      />
    </AutoComplete>
  )
}
