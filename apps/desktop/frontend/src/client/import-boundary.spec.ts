import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const srcDir = join(dirname(fileURLToPath(import.meta.url)), '..')

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

describe('frontend import boundaries', () => {
  it('blocks direct tauri api imports outside client layer', () => {
    const files = walk(srcDir).filter((file) => (file.endsWith('.ts') || file.endsWith('.vue')) && !file.endsWith('.spec.ts'))
    const violations = files.flatMap((file) => {
      const content = readFileSync(file, 'utf8')
      if (file.includes(`${sep}client${sep}`)) return []
      return content.includes("@tauri-apps/api") ? [file] : []
    })

    expect(violations).toEqual([])
  })

  it('blocks fetch and axios in app source', () => {
    const files = walk(srcDir).filter((file) => file.endsWith('.ts') || file.endsWith('.vue'))
    const violations = files.flatMap((file) => {
      const content = readFileSync(file, 'utf8')
      if (file.endsWith('.spec.ts')) return []
      if (content.includes('axios')) return [`axios:${file}`]
      if (content.includes('fetch(')) return [`fetch:${file}`]
      return []
    })

    expect(violations).toEqual([])
  })
})
