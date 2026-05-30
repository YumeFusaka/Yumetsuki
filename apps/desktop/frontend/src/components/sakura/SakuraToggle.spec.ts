import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraToggle from './SakuraToggle.vue'

describe('SakuraToggle', () => {
  it('uses pressed state', () => {
    const wrapper = mount(SakuraToggle, { props: { modelValue: true, ariaLabel: '置顶' } })
    expect(wrapper.attributes('aria-pressed')).toBe('true')
  })
})
