import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SakuraSettingsSection from './SakuraSettingsSection.vue'

describe('SakuraSettingsSection', () => {
  it('renders a section landmark', () => {
    const wrapper = mount(SakuraSettingsSection)
    expect(wrapper.element.tagName).toBe('SECTION')
  })
})
