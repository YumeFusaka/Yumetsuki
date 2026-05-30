import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraTooltip from './SakuraTooltip.vue'

describe('SakuraTooltip', () => {
  it('uses tooltip role', () => {
    const wrapper = mount(SakuraTooltip)
    expect(wrapper.attributes('role')).toBe('tooltip')
  })
})
