import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraButton from './SakuraButton.vue'

describe('SakuraButton', () => {
  it('renders disabled and busy states', () => {
    const wrapper = mount(SakuraButton, {
      props: { disabled: true, busy: true, label: '保存' },
    })

    expect(wrapper.attributes('aria-disabled')).toBe('true')
    expect(wrapper.text()).toContain('保存')
  })
})
