import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraSegmentedControl from './SakuraSegmentedControl.vue'

describe('SakuraSegmentedControl', () => {
  it('marks selected segment', () => {
    const wrapper = mount(SakuraSegmentedControl, { props: { options: ['A'], modelValue: 'A' } })
    expect(wrapper.get('button').attributes('aria-selected')).toBe('true')
  })
})
