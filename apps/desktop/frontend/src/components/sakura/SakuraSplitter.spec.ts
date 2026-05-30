import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraSplitter from './SakuraSplitter.vue'

describe('SakuraSplitter', () => {
  it('is keyboard focusable', () => {
    const wrapper = mount(SakuraSplitter)
    expect(wrapper.attributes('tabindex')).toBe('0')
  })
})
