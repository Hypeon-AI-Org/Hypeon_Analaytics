import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth } from './AuthContext'
import { fetchMe } from '../api'

const UserOrgContext = createContext({
  organizationId: null,
  organizationName: null,
  clientIds: [],
  adChannels: [],
  selectedClientId: null,
  setSelectedClientId: () => {},
  loading: true,
  error: null,
  refetch: () => {},
})

export function useUserOrg() {
  const ctx = useContext(UserOrgContext)
  if (!ctx) throw new Error('useUserOrg must be used within UserOrgProvider')
  return ctx
}

export function UserOrgProvider({ children }) {
  const { user } = useAuth()
  const [organizationId, setOrganizationId] = useState(null)
  const [organizationName, setOrganizationName] = useState(null)
  const [clientIds, setClientIds] = useState([])
  const [adChannels, setAdChannels] = useState([])
  const [selectedClientId, setSelectedClientIdState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!user) {
      setOrganizationId(null)
      setOrganizationName(null)
      setClientIds([])
      setAdChannels([])
      setSelectedClientIdState(null)
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await fetchMe()
      setOrganizationId(data.organization_id ?? null)
      setOrganizationName(data.name ?? null)
      const ids = Array.isArray(data.client_ids) ? data.client_ids : []
      const channels = Array.isArray(data.ad_channels) ? data.ad_channels : []
      setClientIds(ids)
      setAdChannels(channels)
      setSelectedClientIdState((prev) => {
        if (prev != null && ids.includes(prev)) return prev
        return ids.length > 0 ? ids[0] : 1
      })
    } catch (err) {
      setError(err.message || 'Failed to load your organization')
      setClientIds([1])
      setAdChannels([{ client_id: 1, description: 'Default' }])
      setSelectedClientIdState(1)
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    load()
  }, [load])

  const setSelectedClientId = useCallback((id) => {
    setSelectedClientIdState((prev) => (id != null ? id : prev))
  }, [])

  const effectiveClientId = selectedClientId ?? (clientIds.length > 0 ? clientIds[0] : 1)

  const value = {
    organizationId,
    organizationName,
    clientIds,
    adChannels,
    selectedClientId: effectiveClientId,
    setSelectedClientId,
    loading,
    error,
    refetch: load,
  }

  return <UserOrgContext.Provider value={value}>{children}</UserOrgContext.Provider>
}
