import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../services/api'

interface User {
  id: number
  email: string
  username: string
  paper_trading: boolean
  initial_balance: number
  current_balance: number
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const formData = new FormData()
          formData.append('username', username)
          formData.append('password', password)

          const response = await api.post('/auth/login', formData, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
          })

          const { access_token } = response.data
          set({ token: access_token, isAuthenticated: true })
          
          // Fetch user data
          await get().fetchUser()
        } catch (error: any) {
          set({ 
            error: error.response?.data?.detail || 'Login failed',
            isLoading: false 
          })
          throw error
        }
      },

      register: async (email: string, username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          await api.post('/auth/register', { email, username, password })
          // Auto login after registration
          await get().login(username, password)
        } catch (error: any) {
          set({ 
            error: error.response?.data?.detail || 'Registration failed',
            isLoading: false 
          })
          throw error
        }
      },

      logout: () => {
        set({ user: null, token: null, isAuthenticated: false })
      },

      fetchUser: async () => {
        try {
          const response = await api.get('/users/me')
          set({ user: response.data, isLoading: false })
        } catch (error) {
          set({ isLoading: false })
        }
      }
    }),
    {
      name: '100toloose-auth',
      partialize: (state) => ({ token: state.token, isAuthenticated: state.isAuthenticated })
    }
  )
)


