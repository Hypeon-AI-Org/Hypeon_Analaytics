import React, { createContext, useContext, useEffect, useState } from 'react'
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile,
  signOut as firebaseSignOut,
} from 'firebase/auth'
import { auth, isFirebaseConfigured } from '../firebase'
import { setTokenProvider } from '../apiAuth'

const AuthContext = createContext({
  user: null,
  loading: true,
  signIn: async () => {},
  signUp: async () => {},
  sendPasswordReset: async () => {},
  signOut: () => {},
  getIdToken: () => Promise.resolve(null),
  isConfigured: false,
})

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const configured = isFirebaseConfigured()

  useEffect(() => {
    if (!configured) {
      setLoading(false)
      setTokenProvider(null)
      return
    }
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u)
      setLoading(false)
      setTokenProvider(() => (u ? u.getIdToken() : Promise.resolve(null)))
    })
    return () => unsubscribe()
  }, [configured])

  const signIn = async (email, password) => {
    if (!configured) throw new Error('Firebase is not configured')
    return signInWithEmailAndPassword(auth, email, password)
  }

  const signUp = async (email, password, displayName = null) => {
    if (!configured) throw new Error('Firebase is not configured')
    const cred = await createUserWithEmailAndPassword(auth, email, password)
    if (displayName && cred.user) {
      await updateProfile(cred.user, { displayName })
    }
    return cred
  }

  const sendPasswordReset = async (email) => {
    if (!configured) throw new Error('Firebase is not configured')
    return sendPasswordResetEmail(auth, email)
  }

  const signOut = () => {
    if (configured && auth) firebaseSignOut(auth)
    setUser(null)
  }

  const getIdToken = async () => {
    if (!user) return null
    try {
      return await user.getIdToken()
    } catch {
      return null
    }
  }

  const value = {
    user,
    loading,
    signIn,
    signUp,
    sendPasswordReset,
    signOut,
    getIdToken,
    isConfigured: configured,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
