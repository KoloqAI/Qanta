import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './components/AuthProvider'
import { ToastProvider } from './hooks/useToast'
import { AppRouter } from './router'

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRouter />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
