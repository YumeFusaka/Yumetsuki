import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraContextMenu from './SakuraContextMenu.vue'

describe('SakuraContextMenu', () => {
  it('uses menu role', () => {
    const wrapper = mount(SakuraContextMenu)
    expect(wrapper.attributes('role')).toBe('menu')
  })
})
