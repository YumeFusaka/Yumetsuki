import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraTabs from './SakuraTabs.vue'

describe('SakuraTabs', () => {
  it('uses tablist semantics', () => {
    const wrapper = mount(SakuraTabs, { props: { tabs: ['基础'], modelValue: '基础' } })
    expect(wrapper.attributes('role')).toBe('tablist')
  })
})
