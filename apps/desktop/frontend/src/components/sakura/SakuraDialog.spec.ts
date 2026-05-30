import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraDialog from './SakuraDialog.vue'

describe('SakuraDialog', () => {
  it('uses dialog semantics when open', () => {
    const wrapper = mount(SakuraDialog, { props: { open: true, title: '确认' } })
    expect(wrapper.attributes('role')).toBe('dialog')
  })
})
