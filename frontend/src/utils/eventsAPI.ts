export const fetchEvents = async () => {
  const res = await fetch('http://127.0.0.1:8000/events/v1', {
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`
    }
  })

  if (!res.ok) {
    throw new Error('Failed to fetch events')
  }

  return res.json()
}
