import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraSlider from './SakuraSlider.vue'

describe('SakuraSlider', () => {
  it('renders range input', () => {
    const wrapper = mount(SakuraSlider, { props: { ariaLabel: '缩放' } })
    expect(wrapper.attributes('type')).toBe('range')
  })
})
