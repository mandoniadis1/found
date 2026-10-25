import { useEffect, useState } from 'react'
import { api, type Member } from '../api'

const yes = (v: number | boolean, label = '✓') => (v ? <span className="tag ok">{label}</span> : <span className="muted">—</span>)

export function Members() {
  const [items, setItems] = useState<Member[]>([])
  useEffect(() => { api.members().then(setItems) }, [])

  return (
    <>
      <header className="page-head">
        <h1>Members</h1>
        <p className="muted">Everyone with an account, newest first.</p>
      </header>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Email</th><th>Yale email</th><th>LinkedIn</th><th>Moderator</th><th>Startups</th><th>Joined</th></tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.id}>
              <td><strong>{m.first_name} {m.last_name}</strong>{!!m.is_test_account && <span className="tag">test</span>}</td>
              <td>{m.email}</td>
              <td>{yes(m.email_verified, 'verified')}</td>
              <td>{m.linkedin ? <span className={`tag ${m.linkedin_dev_standin ? 'warn' : 'ok'}`}>{m.linkedin_dev_standin ? 'dev stand-in' : m.linkedin_name}</span> : <span className="muted">—</span>}</td>
              <td>{yes(m.is_moderator)}</td>
              <td>{m.startups || <span className="muted">—</span>}</td>
              <td className="muted">{new Date(m.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
