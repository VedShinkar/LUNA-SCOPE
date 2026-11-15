export function siteCode(id: string) {
  return id.replace(/^Site(\d+)$/, 'SITE $1')
}

export function siteName(id: string) {
  return id.replace(/^Site(\d+)$/, 'Site $1')
}
