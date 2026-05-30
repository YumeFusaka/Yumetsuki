import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraSpinBox from './SakuraSpinBox.vue'

describe('SakuraSpinBox', () => {
  it('emits numeric values', async () => {
    const wrapper = mount(SakuraSpinBox)
    await wrapper.get('input').setValue('3')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([3])
  })
})
