import { useEffect, useState } from 'react'
import { createMeasurementHistory, HISTORY_KEY, type HistoryEdit } from './measurement-storage'

export function useMeasurementHistory() {
  const [store] = useState(() => createMeasurementHistory(() => window.localStorage))
  const [history, setHistory] = useState(() => store.snapshot)

  useEffect(() => {
    function sync(event: StorageEvent) {
      if (event.key === HISTORY_KEY || event.key === null) setHistory(store.refresh())
    }
    window.addEventListener('storage', sync)
    setHistory(store.refresh())
    return () => window.removeEventListener('storage', sync)
  }, [store])

  function update(change?: HistoryEdit) {
    const write = () => setHistory(store.edit(change))
    // Serialize read/modify/write across tabs when Web Locks are available.
    if (navigator.locks) void navigator.locks.request(HISTORY_KEY, write).catch(write)
    else write()
  }

  return { history, update }
}
