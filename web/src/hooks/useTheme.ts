import { useState, useEffect } from 'react'
import { getTheme, setTheme as applyTheme, type Theme } from '../theme'

export function useTheme() {
  const [theme, _setTheme] = useState<Theme>(getTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  return { theme, setTheme: _setTheme }
}
