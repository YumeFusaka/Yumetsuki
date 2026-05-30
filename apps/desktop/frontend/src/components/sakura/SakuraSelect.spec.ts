import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraSelect from './SakuraSelect.vue'

describe('SakuraSelect', () => {
  it('renders options', () => {
    const wrapper = mount(SakuraSelect, { props: { options: ['A', 'B'], ariaLabel: '选择' } })
    expect(wrapper.findAll('option')).toHaveLength(2)
  })
})
