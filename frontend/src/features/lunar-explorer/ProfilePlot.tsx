import type { Profile } from '../../services/lunar'

export function ProfilePlot({ profile }: { profile: Profile }) {
  const heights = profile.elevation_m.filter(value => value != null)
  const units = profile.distance_m >= 1000 ? `${(profile.distance_m / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })} km`
    : `${profile.distance_m.toFixed(1)} m`
  const lo = Math.min(...heights), hi = Math.max(...heights)
  const path = profile.elevation_m.map((height, index, values) => height == null ? '' :
    `${index && values[index - 1] != null ? 'L' : 'M'}${4 + 232 * index / (values.length - 1)},${65 - 59 * (height - lo) / (hi - lo || 1)}`
  ).join(' ')
  return <div className="profile-result">
    <div className="profile-distance">{units} <small>surface distance</small></div>
    {heights.length ? <>
      <div className="profile-labels"><span>{Math.round(lo)} m</span><span>{Math.round(hi)} m</span></div>
      <svg viewBox="0 0 240 70" role="img" aria-label="Elevation along the measured path">
        <path d="M4 65 H236" stroke="#46586b" /><path d={path} fill="none" stroke="#85dce3" strokeWidth="1.6" />
      </svg>
    </> : <p className="muted">The path has no valid elevation samples.</p>}
    <p className="muted">{profile.source} · {profile.sampling}</p>
  </div>
}
