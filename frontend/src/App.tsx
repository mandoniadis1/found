import { Link, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { Doodles } from './components/Doodles'
import { VerifyBanner } from './components/VerifyBanner'
import { Login, Signup, Verified } from './pages/AuthPages'
import { Events } from './pages/Events'
import { Explore } from './pages/Explore'
import { Messages } from './pages/Messages'
import { Opportunities } from './pages/Opportunities'
import { Profile } from './pages/Profile'
import { StartupPage } from './pages/StartupPage'

function Nav() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <nav className="nav">
      <Link to="/" className="logo">found<span>.</span></Link>
      <div className="nav-links">
        <NavLink to="/" end>Explore</NavLink>
        <NavLink to="/opportunities">Opportunities</NavLink>
        <NavLink to="/events">Events</NavLink>
        <NavLink to="/messages">Messages</NavLink>
      </div>
      <div className="nav-right">
        {user ? (
          <>
            <NavLink to="/profile" className="nav-user">
              <span className="avatar xs">{user.first_name[0]}{user.last_name[0]}</span>
              {user.first_name}
              {user.linkedin_connected && <span className="verified-dot" title="Signed in with LinkedIn">✓</span>}
            </NavLink>
            <button className="link-btn" onClick={async () => { await logout(); navigate('/') }}>Log out</button>
          </>
        ) : (
          <>
            <NavLink to="/login">Log in</NavLink>
            <Link to="/signup" className="btn btn-dark sm">Join</Link>
          </>
        )}
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <>
      <Doodles />
      <Nav />
      <VerifyBanner />
      <main>
        <Routes>
          <Route path="/" element={<Explore />} />
          <Route path="/startups/:id" element={<StartupPage />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/events" element={<Events />} />
          <Route path="/messages" element={<Messages />} />
          <Route path="/messages/:cid" element={<Messages />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/verified" element={<Verified />} />
        </Routes>
      </main>
      <footer className="footer muted small">found. · built at Yale · startups from the Yale Startup Directory (Yale Pitchbook) · opportunities from the Tsai CITY board</footer>
    </>
  )
}
