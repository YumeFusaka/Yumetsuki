import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraInput from './SakuraInput.vue'

describe('SakuraInput', () => {
  it('emits typed value changes', async () => {
    const wrapper = mount(SakuraInput, { props: { ariaLabel: '输入' } })
    await wrapper.setValue('abc')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['abc'])
  })
})
