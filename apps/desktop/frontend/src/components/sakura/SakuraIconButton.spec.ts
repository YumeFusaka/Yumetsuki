import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraIconButton from './SakuraIconButton.vue'

describe('SakuraIconButton', () => {
  it('requires an accessible label', () => {
    const wrapper = mount(SakuraIconButton, { props: { ariaLabel: '关闭' } })
    expect(wrapper.attributes('aria-label')).toBe('关闭')
  })
})
