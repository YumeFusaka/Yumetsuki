import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraRadioGroup from './SakuraRadioGroup.vue'

describe('SakuraRadioGroup', () => {
  it('uses radiogroup semantics', () => {
    const wrapper = mount(SakuraRadioGroup, { props: { options: ['A'], ariaLabel: '模式' } })
    expect(wrapper.attributes('role')).toBe('radiogroup')
  })
})
