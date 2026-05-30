import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../frontend/src/client/types/rpc.ts', import.meta.url), 'utf8')
const errorSource = readFileSync(new URL('../frontend/src/client/errorCodes.ts', import.meta.url), 'utf8')

function extractArray(name) {
  const match = source.match(new RegExp(`${name}\\s*=\\s*\\[([\\s\\S]*?)\\]`))
  if (!match) {
    throw new Error(`${name} not found`)
  }
  return [...match[1].matchAll(/'([^']+)'/g)].map((item) => item[1])
}

const schemaHash = source.match(/SCHEMA_HASH = '([^']+)'/)?.[1]
if (!schemaHash || !/^[0-9a-f]{64}$/.test(schemaHash)) {
  throw new Error('invalid SCHEMA_HASH')
}

const methods = extractArray('RPC_METHODS')
const events = extractArray('RPC_EVENTS')

if (methods.includes('security.confirm_required')) {
  throw new Error('security.confirm_required must not be an invoke method')
}
if (!events.includes('security.confirm_required')) {
  throw new Error('security.confirm_required must be an event')
}

const cancelMethods = methods.filter((method) => method.includes('cancel'))
if (cancelMethods.length !== 1 || cancelMethods[0] !== 'sidecar.cancel') {
  throw new Error(`invalid cancel method set: ${cancelMethods.join(', ')}`)
}

console.log(`frontend catalog ok (${methods.length} methods, ${events.length} events)`)

const errorCodes = [...errorSource.matchAll(/'([^']+\.[^']+)'/g)].map((item) => item[1])
if (!errorCodes.includes('rpc.protocol_unsupported') || !errorCodes.includes('sidecar.not_ready')) {
  throw new Error('canonical error codes missing')
}
if (new Set(errorCodes).size !== errorCodes.length) {
  throw new Error('duplicate error codes')
}
console.log(`frontend error codes ok (${errorCodes.length} codes)`)
