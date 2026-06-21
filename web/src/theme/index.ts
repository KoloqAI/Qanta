export type Theme = 'system' | 'light' | 'dark'

export function getTheme(): Theme {
  return (localStorage.getItem('quanta-theme') as Theme) || 'system'
}

export function setTheme(theme: Theme): void {
  localStorage.setItem('quanta-theme', theme)
  if (theme === 'system') {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
}
