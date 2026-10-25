import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { timeAgo } from '../format'
import type { Conversation, Message } from '../types'

const POLL_MS = 4000

export function Messages() {
  const { cid } = useParams()
  const active = cid ? Number(cid) : null
  const { user } = useAuth()
  const navigate = useNavigate()
  const [convs, setConvs] = useState<Conversation[]>([])
  const [msgs, setMsgs] = useState<Message[]>([])
  const [text, setText] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!user) return
    const load = () => api.conversations().then(setConvs)
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [user])

  useEffect(() => {
    if (!user || !active) return setMsgs([])
    const load = () => api.messages(active).then(setMsgs).catch(() => navigate('/messages'))
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [user, active, navigate])

  useEffect(() => { endRef.current?.scrollIntoView() }, [msgs.length])

  if (!user) {
    return (
      <div className="page narrow center">
        <p className="serif-lg">Log in to message founders.</p>
        <Link to="/login" className="btn btn-dark">Log in</Link>
      </div>
    )
  }

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!active || !text.trim()) return
    const m = await api.send(active, text)
    setMsgs((all) => [...all, m])
    setText('')
    api.conversations().then(setConvs)
  }

  const current = convs.find((c) => c.id === active)

  return (
    <div className="page">
      <div className="inbox">
        <aside className="inbox-list">
          <h2 className="inbox-title">Messages</h2>
          {convs.length === 0 && <p className="muted small pad">No conversations yet. Open a startup and message its founder.</p>}
          {convs.map((c) => (
            <Link key={c.id} to={`/messages/${c.id}`} className={`conv${c.id === active ? ' on' : ''}`}>
              <div className="avatar sm">{c.other.first_name[0]}{c.other.last_name[0]}</div>
              <div className="conv-text">
                <div className="conv-top">
                  <strong>{c.other.first_name} {c.other.last_name}</strong>
                  <span className="muted small">{timeAgo(c.last_at)}</span>
                </div>
                <p className="muted small ellipsis">{c.last_message ?? 'Say hello 👋'}</p>
              </div>
            </Link>
          ))}
        </aside>

        <section className="thread">
          {!current ? (
            <div className="thread-empty"><p className="serif-lg">Pick a conversation</p></div>
          ) : (
            <>
              <header className="thread-head">
                <div className="avatar sm">{current.other.first_name[0]}{current.other.last_name[0]}</div>
                <div>
                  <strong>{current.other.first_name} {current.other.last_name}</strong>
                  {current.other.linkedin_url && <a className="li-link" href={current.other.linkedin_url} target="_blank" rel="noreferrer">LinkedIn ↗</a>}
                  <p className="muted small">{current.other.headline} · {current.other.school}</p>
                </div>
              </header>
              <div className="thread-body">
                {msgs.map((m) => (
                  <div key={m.id} className={`bubble-row ${m.sender_id === user.id ? 'user' : 'assistant'}`}>
                    <div className={`bubble ${m.sender_id === user.id ? 'user' : 'assistant'}`}>{m.body}</div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <form className="thread-input" onSubmit={send}>
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message ${current.other.first_name}…`} />
                <button className="btn btn-dark" disabled={!text.trim()}>Send</button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
