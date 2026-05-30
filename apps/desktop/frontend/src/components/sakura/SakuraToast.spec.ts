import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraToast from './SakuraToast.vue'

describe('SakuraToast', () => {
  it('announces feedback politely', () => {
    const wrapper = mount(SakuraToast, { slots: { default: '完成' } })
    expect(wrapper.attributes('aria-live')).toBe('polite')
  })
})
